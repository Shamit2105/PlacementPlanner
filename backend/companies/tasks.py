"""
Questions App — Celery Tasks
==============================
All long-running background work runs here so API endpoints stay fast.
"""

import logging
from celery import shared_task
from django.db import transaction
from django.conf import settings
from django.utils import timezone
import time

from .models import Question, Company, ProcessingStatus, QuestionSource,RawScrapedContent
from .scraper import QuestionScraper
from .llm_service import LLMService
from .vector_service import VectorService

logger = logging.getLogger(__name__)


# ─── Pipeline Step 1: Scrape + Extract Questions via LLM ─────────────────────

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
    topic_name: str = "",
    target_count: int = 10,
    trigger_processing: bool = True,
):
    """
    Scrape interview experiences and extract questions using LLM.
    """
    logger.info("Task: scrape_and_ingest | company=%s topic=%s", company_name, topic_name)

    scraper = QuestionScraper()
    try:
        experiences = scraper.scrape_experiences(
            company=company_name,
            target_count=target_count
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
            logger.debug("Raw content already exists for %s — skipping duplicate scrape", exp.get("source_url"))
            # Still extract questions if they weren't extracted before
            existing_count = Question.objects.filter(raw_source=raw_content).count()
            if existing_count > 0:
                skipped += existing_count
                continue
        try:
            extracted_questions = llm.format_questions(
                raw_text=exp["text"],
                company=exp.get("company", company_name),
                topic_hint=topic_name
            )
            
            total_extracted += len(extracted_questions)
            
            # Save each extracted question
            for q_data in extracted_questions:
                question_text = q_data["question"]
                classified_type = q_data["question_type"]
                topic_tags = q_data.get("topic_tags", [])
                
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
                        topic_tags=",".join(topic_tags) if topic_tags else "",
                    )
                    
                    if company_obj:
                        q.companies.add(company_obj)
                
                saved_ids.append(q.pk)
                logger.debug("Saved question pk=%d type=%s tags=%s", q.pk, classified_type, topic_tags)
                
        except Exception as exc:
            logger.error("Failed to extract questions from %s: %s", exp.get('source_url', 'unknown'), exc)
            continue

    logger.info(
        "Scrape complete: %d experiences → %d questions extracted, %d saved, %d skipped",
        len(experiences), total_extracted, len(saved_ids), skipped,
    )

    if trigger_processing:
        for i, qid in enumerate(saved_ids):
            compute_and_store_embedding.apply_async(
                args=[qid],
                countdown=i * 5  
            )

    return {
        "experiences_scraped": len(experiences),
        "questions_extracted": total_extracted,
        "saved": len(saved_ids), 
        "skipped": skipped, 
        "question_ids": saved_ids
    }


# ─── Pipeline Step 3: Answer Generation ───────────────────────────────────────

@shared_task(
    bind=True, 
    max_retries=3, 
    rate_limit="10/m",  
    name="questions.process_single_question"
)
def process_single_question(self, question_id: int):
    """Generate reference answer for an already-formatted question."""
    try:
        q = Question.objects.get(pk=question_id, status=ProcessingStatus.EMBEDDED)
    except Question.DoesNotExist:
        logger.warning(f"Question {question_id} not found or not in EMBEDDED state")
        return

    try:
        llm = LLMService()
        interview_a = llm.generate_answer(q.interview_question, q.question_type)

        q.interview_answer = interview_a
        q.status = ProcessingStatus.PROCESSED
        q.error_log = ""
        q.save(update_fields=["interview_answer", "status", "error_log"])
        time.sleep(1.5)
        logger.info(f"Successfully generated answer for question {question_id}")

    except Exception as exc:
        logger.error("LLM processing failed for question %d: %s", question_id, exc)
        q.status = ProcessingStatus.FAILED
        q.error_log = str(exc)[:1000]
        q.save(update_fields=["status", "error_log"])
        raise self.retry(exc=exc)


# ─── Pipeline Step 2: Compute + Store Embedding ───────────────────────────────

@shared_task(
    bind=True, 
    max_retries=3, 
    name="questions.compute_embedding"
)
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
            logger.info(f"Question {question_id} duplicate of {dup.pk}. Skipping generation.")
            q.is_duplicate = True
            q.status = ProcessingStatus.PROCESSED  
            q.save(update_fields=["is_duplicate", "status"])
        else:
            logger.info(f"Question {question_id} is unique. Proceeding to answer generation.")
            q.status = ProcessingStatus.EMBEDDED
            q.save(update_fields=["status"])
            process_single_question.apply_async(args=[question_id])
            
    except Exception as exc:
        logger.error(f"Embedding failed for question {question_id}: {exc}")
        q.status = ProcessingStatus.FAILED
        q.error_log = str(exc)[:1000]
        q.save(update_fields=["status", "error_log"])
        raise self.retry(exc=exc)


# ─── Pipeline Step 4: Duplicate Detection ────────────────────────────────────

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
        logger.info("Question %d is a near-duplicate of %d — flagging.", question_id, dup.pk)
        Question.objects.filter(pk=question_id).update(is_duplicate=True)


# ─── LLM Generation Fallback ─────────────────────────────────────────────────

@shared_task(
    bind=True,
    max_retries=2,
    default_retry_delay=30,
    name="questions.generate_questions_llm",
    rate_limit="10/m"
)
def generate_questions_via_llm(
    self,
    question_type: str,
    company_name: str = "",
    topic_name: str = "",
    count: int = 5,
):
    """Synthesize questions when scraping methods fall short."""
    logger.info("Generating %d LLM questions | type=%s company=%s topic=%s", count, question_type, company_name, topic_name)

    existing_texts = list(
        Question.objects.filter(question_type=question_type)
                        .values_list("interview_question", flat=True)
                        .exclude(interview_question="")
                        [:50]
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
                topic=topic_name,
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
                    status=ProcessingStatus.PROCESSED,  
                    topic_tags=",".join(result.get("topic_tags", [])) if result.get("topic_tags") else "",
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


# ─── Background Enrichment ───────────────────────────────────────────────────

@shared_task(name="questions.background_enrich")
def background_enrich_for_interview(
    interview_id: int,
    company_name: str = "",
    question_types: list | None = None,
    topics: list | None = None,
):
    """Background task fired immediately after an interview setup instance initialization."""
    MIN_QUESTIONS_THRESHOLD = 15  

    question_types = question_types or [
        "DSA_CODING", "DSA_THEORY", "OS", "DBMS", "NETWORKS", "SYSTEM_DESIGN"
    ]
    topics = topics or []

    logger.info("Background enrichment for interview %d | company=%s", interview_id, company_name)

    qs = Question.objects.filter(is_duplicate=False, status=ProcessingStatus.PROCESSED)
    if company_name:
        qs = qs.filter(companies__slug=company_name.lower().replace(" ", "-"))
    
    total_count = qs.count()
    
    if total_count < MIN_QUESTIONS_THRESHOLD:
        shortfall = MIN_QUESTIONS_THRESHOLD - total_count
        topic = topics[0] if topics else ""

        logger.info("Enriching bank — only %d total questions, need %d more", total_count, shortfall)

        scrape_result = scrape_and_ingest_questions.apply_async(
            kwargs={
                "question_type": "",  
                "company_name": company_name,
                "topic_name": topic,
                "target_count": max(shortfall + 5, 10),  
                "trigger_processing": True,
            }
        )
        
        scraped_count = 0
        try:
            result = scrape_result.get(timeout=120)
            scraped_count = result.get("saved", 0)
        except Exception:
            logger.warning("Could not get scraping result in time — continuing")

        still_needed = shortfall - scraped_count
        if still_needed > 0:
            generate_questions_via_llm.delay(
                question_type="DSA_CODING",
                company_name=company_name,
                topic_name=topic,
                count=min(still_needed, 5),  
            )
    else:
        logger.info("Bank already has %d questions — no enrichment needed", total_count)