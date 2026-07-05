"""
Interview Service — question selection, answer evaluation, scoring.
"""

import logging

from companies.llm_service import LLMService
from companies.models import Company, ProcessingStatus, Question
from django.db.models import Q

logger = logging.getLogger(__name__)


def normalize_verdict(verdict, score) -> str:
    """Return one of the short verdicts supported by InterviewQuestion."""
    normalized = str(verdict or "").strip().lower()
    if normalized in {"strong", "acceptable", "needs work"}:
        return normalized.title()

    try:
        numeric_score = float(score)
    except (TypeError, ValueError):
        numeric_score = 0

    if numeric_score >= 8:
        return "Strong"
    if numeric_score >= 5:
        return "Acceptable"
    return "Needs Work"


class InterviewService:
    """Handles interview session logic."""

    def __init__(self):
        self.llm = LLMService()

    def select_questions(
        self,
        company_slug: str = "",
        question_types: list | None = None,
        count: int = 1,
        exclude_ids: list | None = None,
        difficulty: str | None = None,
        user=None,
    ) -> list:
        # Default to DSA_CODING if not provided
        question_types = question_types or ["DSA_CODING"]

        qs = Question.objects.filter(
            status=ProcessingStatus.PROCESSED,
            is_duplicate=False,
            question_type__in=question_types,
        )

        if company_slug:
            qs = qs.filter(companies__slug=company_slug)

        if exclude_ids:
            qs = qs.exclude(pk__in=exclude_ids)

        if user and hasattr(user, "profile"):
            passed_q_ids = user.profile.questions_passed.values_list("id", flat=True)
            if passed_q_ids:
                qs = qs.exclude(pk__in=passed_q_ids)

        if difficulty:
            # Assume Difficulty enum values are upper case strings like "EASY", "MEDIUM", "HARD"
            qs = qs.filter(difficulty=difficulty.upper())

        selected = list(qs.order_by("?")[:count])

        # If not enough questions of the requested difficulty, fall back to any difficulty
        if len(selected) < count and difficulty:
            shortfall = count - len(selected)
            logger.info(
                f"Not enough questions for difficulty {difficulty}, filling with any difficulty ({shortfall} more)."
            )
            # Re‑query without difficulty filter, excluding already selected ids
            existing_ids = [q.id for q in selected]
            filler_qs = Question.objects.filter(
                status=ProcessingStatus.PROCESSED,
                is_duplicate=False,
                question_type__in=question_types,
            )
            if company_slug:
                filler_qs = filler_qs.filter(companies__slug=company_slug)
            if exclude_ids:
                filler_qs = filler_qs.exclude(pk__in=exclude_ids)
            if user and hasattr(user, "profile"):
                passed_q_ids = user.profile.questions_passed.values_list(
                    "id", flat=True
                )
                if passed_q_ids:
                    filler_qs = filler_qs.exclude(pk__in=passed_q_ids)
            if existing_ids:
                filler_qs = filler_qs.exclude(pk__in=existing_ids)
            filler = list(filler_qs.order_by("?")[:shortfall])
            selected.extend(filler)

        # Ensure we have the desired count
        selected = selected[:count]

        # Generate missing reference answers if needed
        for q in selected:
            if not q.interview_answer:
                logger.info(
                    f"Generating missing reference answer for Question {q.pk} before starting interview..."
                )
                try:
                    ans = self.llm.generate_answer(
                        q.interview_question, q.question_type
                    )
                    q.interview_answer = ans
                    q.save(update_fields=["interview_answer"])
                except Exception as e:
                    logger.error(f"Failed to generate answer for Question {q.pk}: {e}")

        # Shuffle to avoid deterministic ordering
        import random

        random.shuffle(selected)
        return selected

    def evaluate_answer(
        self,
        interview_question: str,
        evaluation_rubric: dict,
        candidate_answer: str,
        question_type: str,
    ) -> dict:
        """Evaluate a candidate answer against the question's rubric."""
        evaluation = self.llm.evaluate_answer(
            question=interview_question,
            rubric=evaluation_rubric,
            candidate_answer=candidate_answer,
            question_type=question_type,
        )
        evaluation["verdict"] = normalize_verdict(
            evaluation.get("verdict"), evaluation.get("score")
        )
        return evaluation
