"""
Vector Service — pgvector Semantic Search
==========================================
Handles:
  1. Storing embeddings in the Question model's VectorField
  2. Semantic similarity search: find questions similar to a text query
  3. Cosine-similarity deduplication: detect near-duplicate questions
  4. Fetching a smart question set for a mock interview by semantic relevance

WHY pgvector?
  • Native Postgres extension → no separate vector database to manage
  • Supports cosine, L2, and inner-product distance operators
  • IVFFlat index: approximate nearest-neighbor search in O(log n)
  • Integrates cleanly with Django ORM via the pgvector package

DISTANCE OPERATORS in pgvector Django:
  CosineDistance  — best for text embeddings (ignores magnitude)
  L2Distance      — Euclidean, good for dense feature vectors
  MaxInnerProduct — inner product, used when vectors are unit-normalized

We use CosineDistance throughout because embeddings are unit-normalized.

"""

import logging
from typing import Optional

from pgvector.django import CosineDistance
from django.db.models import QuerySet


from .models import Question, ProcessingStatus

logger = logging.getLogger(__name__)

# Cosine distance threshold for considering two questions "duplicates"
# cosine_distance = 1 - cosine_similarity
# distance < 0.05 means similarity > 0.95 → almost identical
DUPLICATE_DISTANCE_THRESHOLD = 0.05

# Distance threshold for "semantically related" (used in interview set selection)
RELATED_DISTANCE_THRESHOLD = 0.35


class VectorService:
    """
    Service class for all pgvector operations.
    Import and use in Celery tasks and views.
    """

    def store_embedding(self, question_id: int, embedding: list[float]) -> bool:
        """
        Save a computed Gemini embedding to the Question's VectorField.

        WHY store rather than compute on-the-fly?
          Gemini embedding API has a 1 RPM limit on the free tier.
          Pre-computing and storing means search is instant (just a DB query)
          instead of waiting 65 seconds per query for the embedding.

        Args:
            question_id: PK of the Question instance.
            embedding: 768-dim float list from LLMService.get_embedding().

        Returns:
            True on success, False on failure.
        """
        

        try:
            updated = Question.objects.filter(pk=question_id).update(
                embedding=embedding,
                status=ProcessingStatus.EMBEDDED,
            )
            if updated:
                logger.info("Stored embedding for question %d", question_id)
            return bool(updated)
        except Exception as exc:
            logger.error("Failed to store embedding for question %d: %s", question_id, exc)
            return False

    def semantic_search(
        self,
        query_embedding: list[float],
        question_type: Optional[str] = None,
        company_slug: Optional[str] = None,
        limit: int = 10,
    ) -> QuerySet:
        """
        Find the most semantically similar questions to a query embedding.

        Uses pgvector's CosineDistance operator which maps to the <=> operator
        in PostgreSQL. The ORM call translates to:
          SELECT * FROM questions_question
          ORDER BY embedding <=> '[0.1, 0.2, ...]'::vector
          LIMIT 10;

        Args:
            query_embedding: 768-dim vector from LLMService.get_query_embedding().
            question_type: Optional filter to restrict by category.
            company_slug: Optional filter to restrict by company.
            limit: Max results to return.

        Returns:
            QuerySet of Question objects annotated with 'distance' field.
            Lower distance = more similar (distance 0 = identical).
        """

        qs = Question.objects.filter(
            status=ProcessingStatus.EMBEDDED,   # only questions with stored embeddings
            is_duplicate=False,                  # skip known duplicates
            embedding__isnull=False,
        )

        if question_type:
            qs = qs.filter(question_type=question_type)

        if company_slug:
            qs = qs.filter(companies__slug=company_slug)

        # Annotate with cosine distance and order by it (ascending = most similar first)
        qs = (
            qs.annotate(distance=CosineDistance("embedding", query_embedding))
              .order_by("distance")
              [:limit]
        )

        logger.debug(
            "Semantic search returned %d results for type=%s company=%s",
            qs.count(), question_type, company_slug,
        )
        return qs

    def find_duplicates(
        self,
        embedding: list[float],
        exclude_id: Optional[int] = None,
    ) -> QuerySet:
        """
        Find existing questions that are near-duplicates of a given embedding.

        Used in the ingestion pipeline to flag newly scraped/generated questions
        that are too similar to what's already in the bank.

        A question is a "duplicate" if cosine distance < DUPLICATE_DISTANCE_THRESHOLD
        (i.e., cosine similarity > 0.95).

        Args:
            embedding: The embedding of the new question.
            exclude_id: Question ID to exclude from comparison (itself).

        Returns:
            QuerySet of Question objects that are near-duplicates.
        """
        from .models import Question, ProcessingStatus

        qs = Question.objects.filter(
            status=ProcessingStatus.EMBEDDED,
            embedding__isnull=False,
        )
        if exclude_id:
            qs = qs.exclude(pk=exclude_id)

        duplicates = (
            qs.annotate(distance=CosineDistance("embedding", embedding))
              .filter(distance__lt=DUPLICATE_DISTANCE_THRESHOLD)
              .order_by("distance")
        )
        return duplicates

    def get_interview_question_set(
        self,
        query_embedding: list[float],
        question_types: list[str],
        company_slug: Optional[str] = None,
        total_questions: int = 10,
    ) -> QuerySet:
        """
        Assemble a smart interview question set using semantic search.

        WHY this instead of random selection?
          Random selection might give you 5 identical-topic questions.
          Semantic search lets us pick questions that are relevant to the
          company/topic but diverse (by selecting one question per similarity
          cluster). We also respect the question_type distribution the user asked for.

        Strategy:
          • Divide total_questions proportionally among requested question_types
          • For each type, do a semantic search and pick top-k
          • Merge and shuffle the final set

        Args:
            query_embedding: Embedding of the combined company+topic query.
            question_types: List of QuestionType values to include.
            company_slug: Restrict to questions tagged for this company.
            total_questions: Target interview length.

        Returns:
            QuerySet (or list) of Question objects.
        """

        if not question_types:
            question_types = ["DSA_CODING", "DSA_THEORY", "OS", "DBMS",
                              "NETWORKS", "SYSTEM_DESIGN"]

        per_type = max(1, total_questions // len(question_types))
        all_ids  = []

        for qtype in question_types:
            results = self.semantic_search(
                query_embedding=query_embedding,
                question_type=qtype,
                company_slug=company_slug,
                limit=per_type + 2,  # fetch a couple extra to allow filtering
            )
            all_ids.extend([q.pk for q in results[:per_type]])

        # Deduplicate IDs (a question might appear in multiple type searches)
        unique_ids = list(dict.fromkeys(all_ids))[:total_questions]

        # Preserve ordering from the semantic search
        questions = Question.objects.filter(pk__in=unique_ids)
        pk_order  = {pk: idx for idx, pk in enumerate(unique_ids)}
        return sorted(questions, key=lambda q: pk_order.get(q.pk, 999))

    def get_similar_questions(
        self,
        question_id: int,
        limit: int = 5,
    ) -> QuerySet:
        """
        "You might also like" feature — find questions semantically similar
        to a given question. Uses the stored embedding of the question itself.

        Args:
            question_id: The reference question's PK.
            limit: Number of similar questions to return.

        Returns:
            QuerySet of similar Question objects (excludes the reference question).
        """

        try:
            ref = Question.objects.get(pk=question_id, embedding__isnull=False)
        except Question.DoesNotExist:
            logger.warning("Question %d not found or has no embedding", question_id)
            return Question.objects.none()

        return (
            Question.objects.filter(embedding__isnull=False)
                            .exclude(pk=question_id)
                            .annotate(distance=CosineDistance("embedding", ref.embedding))
                            .order_by("distance")
                            [:limit]
        )
