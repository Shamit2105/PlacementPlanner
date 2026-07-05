import logging
import time

from celery import shared_task
from django.db import transaction

from .llm_service import LLMService
from .models import (
    Company,
    ProcessingStatus,
    Question,
    QuestionSource,
    RawScrapedContent,
)
from .scraper import QuestionScraper
from .vector_service import VectorService

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=120,
    rate_limit="10/m",
    name="questions.scrape_and_ingest",
)
def scrape_and_ingest_questions(
    self,
    question_type: str = "",
    company_name: str = "",
    target_count: int = 10,
    trigger_processing: bool = True,
):
    """
    Scrape interview experiences and extract questions using LLM.
    """
    logger.info(
        "Task: scrape_and_ingest | company=%s type=%s",
        company_name,
        question_type,
    )

    scraper = QuestionScraper()
    try:
        experiences = scraper.scrape_experiences(
            company=company_name,
            target_count=target_count,
            question_type=question_type,
        )
    except Exception as exc:
        logger.error("Scraping failed: %s", exc)
        raise self.retry(exc=exc)

    # --- ADD TRANSACTION PROTECTION FOR COMPANY LOOKUP ---
    company_obj = None
    if company_name:
        with transaction.atomic():
            company_obj, _ = Company.objects.get_or_create(
                slug=company_name.lower().replace(" ", "-"),
                defaults={"name": company_name},
            )

    llm = LLMService()
    saved_ids = []
    skipped = 0
    total_extracted = 0

    for exp in experiences:
        raw_content, created = RawScrapedContent.objects.get_or_create(
            source_url=exp.get("source_url", ""),
            defaults={
                "raw_text": exp["text"],
                "company": exp.get("company", company_name),
            },
        )

        if not created:
            logger.debug(
                "Raw content already exists for %s — checking for missing questions",
                exp.get("source_url"),
            )
            # Re-run extraction so pages ingested by older, type-filtered jobs
            # can be backfilled. The question-level duplicate check below keeps
            # already saved questions from being inserted again.
        try:
            extracted_questions = llm.format_questions(
                raw_text=raw_content.raw_text,
                company=exp.get("company", company_name),
            )

            total_extracted += len(extracted_questions)

            # Save every question found on the page. ``question_type`` only
            # influences which pages are discovered; it must not discard
            # other categories that occur in the same interview experience.
            for q_data in extracted_questions:
                question_text = q_data["question"]
                classified_type = q_data["question_type"]

                if Question.objects.filter(interview_question=question_text).exists():
                    skipped += 1
                    continue

                # --- WRAP THE ENTITY AND RELATIONSHIP CREATION IN AN ATOMIC BLOCK ---
                with transaction.atomic():
                    q = Question.objects.create(
                        raw_source=raw_content,
                        interview_question=question_text,
                        question_type=classified_type,
                        source=exp["source"],
                        source_url=exp.get("source_url", ""),
                        status=ProcessingStatus.SCRAPED,
                    )

                    if company_obj:
                        q.companies.add(company_obj)

                saved_ids.append(q.pk)
                logger.debug("Saved question pk=%d type=%s", q.pk, classified_type)

        except Exception as exc:
            logger.error(
                "Failed to extract questions from %s: %s",
                exp.get("source_url", "unknown"),
                exc,
            )
            continue

    logger.info(
        "Scrape complete: %d experiences → %d questions extracted, %d saved, %d skipped",
        len(experiences),
        total_extracted,
        len(saved_ids),
        skipped,
    )

    if trigger_processing:
        for i, qid in enumerate(saved_ids):
            compute_and_store_embedding.apply_async(args=[qid], countdown=i * 5)

    return {
        "experiences_scraped": len(experiences),
        "questions_extracted": total_extracted,
        "saved": len(saved_ids),
        "skipped": skipped,
        "question_ids": saved_ids,
    }


@shared_task(
    bind=True,
    max_retries=3,
    rate_limit="10/m",
    name="questions.process_single_question",
)
def process_single_question(self, question_id: int):
    """to generate reference answer for an already-formatted question."""
    try:
        q = Question.objects.get(pk=question_id, status=ProcessingStatus.EMBEDDED)
    except Question.DoesNotExist:
        logger.warning(f"Question {question_id} not found or not in EMBEDDED state")
        return

    try:
        llm = LLMService()
        interview_a = llm.generate_answer(q.interview_question, q.question_type)
        rubric = llm.generate_evaluation_rubric(
            q.interview_question,
            q.question_type,
        )

        q.interview_answer = interview_a
        q.evaluation_rubric = rubric
        q.status = ProcessingStatus.PROCESSED
        q.error_log = ""
        q.save(
            update_fields=[
                "interview_answer",
                "evaluation_rubric",
                "status",
                "error_log",
            ]
        )
        time.sleep(1.5)
        logger.info(f"Successfully generated answer for question {question_id}")

    except Exception as exc:
        logger.error("LLM processing failed for question %d: %s", question_id, exc)
        q.status = ProcessingStatus.FAILED
        q.error_log = str(exc)[:1000]
        q.save(update_fields=["status", "error_log"])
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, name="questions.compute_embedding")
def compute_and_store_embedding(self, question_id: int):
    """Compute embedding vector for a question and store it."""
    try:
        q = Question.objects.get(pk=question_id, status=ProcessingStatus.SCRAPED)
    except Question.DoesNotExist:
        logger.warning(f"Question {question_id} not found or not in SCRAPED state")
        return

    text_to_embed = q.interview_question if q.interview_question else q.raw_source

    try:
        llm = LLMService()
        embedding = llm.get_embedding(text_to_embed)

        if embedding is None:
            raise ValueError("Failed to generate embedding")

        vs = VectorService()
        vs.store_embedding(question_id, embedding)

        # Immediate Semantic Deduplication Lookup
        duplicates = vs.find_duplicates(embedding=embedding, exclude_id=question_id)
        if duplicates.exists():
            dup = duplicates.first()
            logger.info(
                f"Question {question_id} duplicate of {dup.pk}. Skipping generation."
            )
            q.is_duplicate = True
            q.status = ProcessingStatus.PROCESSED
            q.save(update_fields=["is_duplicate", "status"])
        else:
            logger.info(
                f"Question {question_id} is unique. Proceeding to answer generation."
            )
            q.status = ProcessingStatus.EMBEDDED
            q.save(update_fields=["status"])
            process_single_question.apply_async(args=[question_id])

    except Exception as exc:
        logger.error(f"Embedding failed for question {question_id}: {exc}")
        q.status = ProcessingStatus.FAILED
        q.error_log = str(exc)[:1000]
        q.save(update_fields=["status", "error_log"])
        raise self.retry(exc=exc)


@shared_task(name="questions.check_duplicates")
def check_and_flag_duplicates(question_id: int):
    """Post-embedding cleanup semantic checker."""
    try:
        q = Question.objects.get(pk=question_id, status=ProcessingStatus.EMBEDDED)
    except Question.DoesNotExist:
        return

    if q.embedding is None:
        return

    vs = VectorService()
    duplicates = vs.find_duplicates(embedding=q.embedding, exclude_id=question_id)

    if duplicates.exists():
        dup = duplicates.first()
        logger.info(
            "Question %d is a near-duplicate of %d — flagging.", question_id, dup.pk
        )
        Question.objects.filter(pk=question_id).update(is_duplicate=True)


@shared_task(
    bind=True,
    max_retries=2,
    default_retry_delay=30,
    name="questions.generate_questions_llm",
    rate_limit="10/m",
)
def generate_questions_via_llm(
    self,
    question_type: str,
    company_name: str = "",
    count: int = 5,
):
    """Synthesize questions when scraping methods fall short."""
    logger.info(
        "Generating %d LLM questions | type=%s company=%s",
        count,
        question_type,
        company_name,
    )

    existing_texts = list(
        Question.objects.filter(question_type=question_type)
        .values_list("interview_question", flat=True)
        .exclude(interview_question="")[:50]
    )

    company_obj = None
    if company_name:
        with transaction.atomic():
            company_obj, _ = Company.objects.get_or_create(
                slug=company_name.lower().replace(" ", "-"),
                defaults={"name": company_name},
            )

    llm = LLMService()
    saved_ids = []

    for i in range(count):
        try:
            result = llm.generate_unique_question(
                question_type=question_type,
                company=company_name,
                existing_questions=existing_texts,
            )

            with transaction.atomic():
                q = Question.objects.create(
                    raw_source=None,
                    interview_question=result.get("question", ""),
                    interview_answer=result.get("answer", ""),
                    question_type=question_type,
                    difficulty=result.get("difficulty", "Medium").upper(),
                    source=QuestionSource.GENERATED,
                    status=ProcessingStatus.SCRAPED,
                )
                if company_obj:
                    q.companies.add(company_obj)

            saved_ids.append(q.pk)
            existing_texts.append(result.get("question", ""))

            compute_and_store_embedding.apply_async(
                args=[q.pk],
                countdown=i * 5,
            )

        except Exception as exc:
            logger.error("LLM generation iteration %d failed: %s", i, exc)
            continue

    return {"generated": len(saved_ids), "question_ids": saved_ids}
