import logging

from django.db import transaction

from .llm_service import LLMService
from .models import (
    Company,
    ProcessingStatus,
    Question,
    QuestionSource,
    RawScrapedContent,
)
from .vector_service import VectorService

logger = logging.getLogger(__name__)


class QuestionPipeline:
    def __init__(self):
        self.llm = LLMService()
        self.vector = VectorService()

    def extract_questions(
        self,
        experience: dict,
        company_name: str = "",
        question_type: str = "",
    ):
        raw, _ = RawScrapedContent.objects.get_or_create(
            source_url=experience.get("source_url", ""),
            defaults={
                "raw_text": experience["text"],
                "company": experience.get("company", company_name),
            },
        )

        extracted = self.llm.format_questions(
            raw_text=raw.raw_text,
            company=experience.get("company", company_name),
        )

        ids = []
        company = None

        if company_name:
            company, _ = Company.objects.get_or_create(
                slug=company_name.lower().replace(" ", "-"),
                defaults={"name": company_name},
            )

        # Persist all categories extracted from this page. question_type is a
        # discovery hint, not a filter on a mixed-topic interview experience.
        for q in extracted:
            question = q["question"].strip()
            if Question.objects.filter(interview_question=question).exists():
                continue

            with transaction.atomic():
                obj = Question.objects.create(
                    raw_source=raw,
                    interview_question=question,
                    question_type=q["question_type"],
                    source=experience.get("source") or QuestionSource.GFG,
                    source_url=experience.get("source_url", ""),
                    status=ProcessingStatus.SCRAPED,
                )

                if company:
                    obj.companies.add(company)

            ids.append(obj.pk)

        return ids
