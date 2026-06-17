"""
Questions App — Views
=======================
REST API endpoints for the question bank.

Endpoints:
  GET    /api/v1/questions/                → paginated list with filters
  POST   /api/v1/questions/                → manually add a question
  GET    /api/v1/questions/<id>/           → full detail with reference answer
  DELETE /api/v1/questions/<id>/           → remove question
  POST   /api/v1/questions/semantic-search/ → vector similarity search
  POST   /api/v1/questions/scrape/          → trigger background scrape task
  GET    /api/v1/questions/companies/       → list all companies
  POST   /api/v1/questions/companies/       → create company
  GET    /api/v1/questions/topics/          → list all topics
  GET    /api/v1/questions/<id>/similar/    → find semantically similar questions

Design decisions:
  • Semantic search is a POST (not GET) because the query string embedding is
    computed on request — idempotent but with a side effect (LLM call).
  • Scraping is always async (returns task_id for polling).
  • List endpoint hides embedding and raw question_text for performance.
"""

import logging

from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import generics, status, filters
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.views import APIView
from celery.result import AsyncResult


from .llm_service import LLMService
from .vector_service import VectorService
from .filters import QuestionFilter
from .models import Company, Question, Topic, ProcessingStatus
from .serializers import (
    CompanySerializer,
    QuestionCreateSerializer,
    QuestionDetailSerializer,
    QuestionListSerializer,
    SemanticSearchSerializer,
    ScrapeRequestSerializer,
    TopicSerializer,
)
from .tasks import scrape_and_ingest_questions

logger = logging.getLogger(__name__)


# ─── Company Endpoints ────────────────────────────────────────────────────────

class CompanyListCreateView(generics.ListCreateAPIView):
    """
    GET  /companies/ → list all companies (for autocomplete in frontend)
    POST /companies/ → create a new company entry
    """
    queryset         = Company.objects.all()
    serializer_class = CompanySerializer
    filter_backends  = [filters.SearchFilter, filters.OrderingFilter]
    search_fields    = ["name", "slug"]
    ordering_fields  = ["name", "created_at"]


# ─── Topic Endpoints ──────────────────────────────────────────────────────────

class TopicListCreateView(generics.ListCreateAPIView):
    """
    GET  /topics/ → list all topics, optionally filtered by question_type
    POST /topics/ → create a topic
    """
    serializer_class = TopicSerializer
    filter_backends  = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ["question_type"]
    search_fields    = ["name"]

    def get_queryset(self):
        return Topic.objects.all().order_by("question_type", "name")


# ─── Question List + Create ───────────────────────────────────────────────────

class QuestionListCreateView(generics.ListCreateAPIView):
    """
    GET  /questions/
      Query params:
        question_type  — filter by category (DSA_CODING, OS, etc.)
        status         — SCRAPED | PROCESSED | EMBEDDED | FAILED
        source         — LC | GFG | GENERATED
        company        — company slug
        topic          — topic id
        is_duplicate   — true/false
        difficulty     — EASY | MEDIUM | HARD
        search         — full-text search on interview_question
        ordering       — times_used, created_at, difficulty

    POST /questions/
      Body: QuestionCreateSerializer fields
      → Saves question and fires process_single_question Celery task
    """
    filter_backends  = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class  = QuestionFilter
    search_fields    = ["interview_question",]
    ordering_fields  = ["times_used", "created_at", "difficulty"]
    ordering         = ["-created_at"]

    def get_queryset(self):
        return (
            Question.objects.filter(is_duplicate=False)
                            .prefetch_related("companies", "topics")
                            .defer("embedding",  "interview_answer")
        )

    def get_serializer_class(self):
        if self.request.method == "POST":
            return QuestionCreateSerializer
        return QuestionListSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        question = serializer.save()
        return Response(
            QuestionDetailSerializer(question).data,
            status=status.HTTP_201_CREATED,
        )


# ─── Question Detail / Delete ─────────────────────────────────────────────────

class QuestionDetailView(generics.RetrieveDestroyAPIView):
    """
    GET    /questions/<id>/ → full detail including reference answer
    DELETE /questions/<id>/ → remove from bank
    """
    queryset         = Question.objects.prefetch_related("companies", "topics")
    serializer_class = QuestionDetailSerializer

class GenerateAnswerView(APIView):
    """
    POST /questions/<id>/generate-answer/
    Generates an interview_answer for a question if it doesn't exist.
    """
    def post(self, request, pk):
        try:
            question = Question.objects.get(pk=pk)
        except Question.DoesNotExist:
            return Response({"error": "Question not found."}, status=status.HTTP_404_NOT_FOUND)

        if question.interview_answer:
            return Response({"message": "Answer already exists.", "answer": question.interview_answer})

        try:
            llm = LLMService()
            ans = llm.generate_answer(question.interview_question, question.question_type)
            question.interview_answer = ans
            question.save(update_fields=["interview_answer"])
            return Response({"message": "Answer generated.", "answer": ans})
        except Exception as e:
            logger.error(f"Failed to generate answer for Question {pk}: {e}")
            return Response({"error": "Failed to generate answer."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ─── Semantic Search ──────────────────────────────────────────────────────────

class SemanticSearchView(APIView):
    """
    POST /questions/semantic-search/

    Find questions semantically similar to a text query using pgvector
    cosine distance on stored Gemini embeddings.

    Body:
      query         (str)  — the search query e.g. "explain quicksort"
      question_type (str)  — optional filter
      company_slug  (str)  — optional filter
      limit         (int)  — max results (default 10)

    WHY POST instead of GET?
      Computing the query embedding requires a Gemini API call which may
      take a few seconds. Caching by query string would help but we keep
      it simple for now. Also, query text can be long.

    NOTE: This endpoint calls Gemini embedding API (1 RPM free tier).
    In production, add caching (Redis) on the query text → embedding lookup.
    """

    def post(self, request):
        serializer = SemanticSearchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data



        try:
            llm = LLMService()
            query_embedding = llm.get_query_embedding(data["query"])
        except Exception as exc:
            logger.error("Embedding computation failed: %s", exc)
            return Response(
                {"error": "Failed to compute query embedding. Try again shortly."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        if query_embedding is None:
            return Response(
                {"error": "Embedding returned None. Gemini may be rate-limiting."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        vs      = VectorService()
        results = vs.semantic_search(
            query_embedding=query_embedding,
            question_type=data.get("question_type") or None,
            company_slug=data.get("company_slug") or None,
            limit=data.get("limit", 10),
        )

        # Annotate results with the cosine distance for frontend display
        questions_data = []
        for q in results:
            q_data = QuestionListSerializer(q).data
            q_data["similarity_score"] = round(1 - getattr(q, "distance", 1.0), 4)
            questions_data.append(q_data)

        return Response({"count": len(questions_data), "results": questions_data})


# ─── Similar Questions ────────────────────────────────────────────────────────

class SimilarQuestionsView(APIView):
    """
    GET /questions/<id>/similar/

    Returns questions semantically similar to the given question.
    Uses the stored embedding of the reference question, so no Gemini call needed.
    This is fast (pure DB query via pgvector).
    """

    def get(self, request, pk):
        limit = int(request.query_params.get("limit", 5))
        vs      = VectorService()
        results = vs.get_similar_questions(question_id=pk, limit=limit)
        
        data = []
        for q in results:
            q_data = QuestionListSerializer(q).data
            q_data["similarity_score"] = round(1 - getattr(q, "distance", 1.0), 4)
            data.append(q_data)
            
        return Response({"count": len(data), "results": data})


# ─── Scrape Trigger ──────────────────────────────────────────────────────────

class TriggerScrapeView(APIView):
    """
    POST /questions/scrape/

    Manually trigger a scraping job for a question type + company/topic.
    Returns a task_id that can be polled at /api/v1/tasks/<task_id>/status/.

    Body:
      question_type (str, required)
      company_name  (str, optional)
      topic_name    (str, optional)
      target_count  (int, optional, default 10)

    Useful for:
      • Pre-seeding the question bank before launch
      • Admin triggering enrichment for a new company
    """

    def post(self, request):
        serializer = ScrapeRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        task = scrape_and_ingest_questions.delay(
            question_type=data["question_type"],
            company_name=data.get("company_name", ""),
            topic_name=data.get("topic_name", ""),
            target_count=data.get("target_count", 10),
        )

        return Response(
            {
                "message": "Scraping task queued.",
                "task_id": task.id,
                "poll_url": f"/api/v1/tasks/{task.id}/status/",
            },
            status=status.HTTP_202_ACCEPTED,
        )


# ─── Celery Task Status Polling ──────────────────────────────────────────────

@api_view(["GET"])
def task_status_view(request, task_id):
    """
    GET /api/v1/tasks/<task_id>/status/

    Poll the status of a Celery background task.
    Useful for the frontend to show a progress indicator.

    States: PENDING | STARTED | SUCCESS | FAILURE | RETRY
    """
    result = AsyncResult(task_id)
    response = {
        "task_id": task_id,
        "status": result.status,
    }
    if result.ready():
        if result.successful():
            response["result"] = result.result
        else:
            response["error"] = str(result.result)

    return Response(response)


# ─── Question Bank Stats ─────────────────────────────────────────────────────

@api_view(["GET"])
def question_bank_stats(request):
    """
    GET /api/v1/questions/stats/

    Returns counts by type, source, and status.
    Used by the admin dashboard to monitor bank health.
    """
    from django.db.models import Count
    from .models import QuestionType

    by_type = dict(
        Question.objects.filter(is_duplicate=False)
                        .values_list("question_type")
                        .annotate(count=Count("id"))
                        .values_list("question_type", "count")
    )
    by_status = dict(
        Question.objects.values_list("status")
                        .annotate(count=Count("id"))
                        .values_list("status", "count")
    )
    by_source = dict(
        Question.objects.filter(is_duplicate=False)
                        .values_list("source")
                        .annotate(count=Count("id"))
                        .values_list("source", "count")
    )
    embedded_pct = (
        Question.objects.filter(status=ProcessingStatus.EMBEDDED).count()
        / max(Question.objects.count(), 1)
        * 100
    )

    return Response({
        "total": Question.objects.count(),
        "unique": Question.objects.filter(is_duplicate=False).count(),
        "embedded_percent": round(embedded_pct, 1),
        "by_type": by_type,
        "by_status": by_status,
        "by_source": by_source,
    })
