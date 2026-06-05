"""
Interview Service — question selection, answer evaluation, scoring.
"""
import logging
from django.db.models import Q
from companies.models import Question, Company, ProcessingStatus
from companies.llm_service import LLMService

logger = logging.getLogger(__name__)


class InterviewService:
    """Handles interview session logic."""
    
    def __init__(self):
        self.llm = LLMService()
    
    def select_questions(
        self,
        company_slug: str = "",
        question_types: list | None = None,
        count: int = 5,
        exclude_ids: list | None = None,
    ) -> list:
        """
        Select questions for an interview session.
        
        Strategy:
        1. Filter by company + question types
        2. Prioritize questions that haven't been used much
        3. Mix difficulties (30% Easy, 50% Medium, 20% Hard)
        """
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
        
        # Mix by difficulty
        easy_count = max(1, int(count * 0.3))
        medium_count = max(1, int(count * 0.5))
        hard_count = count - easy_count - medium_count
        
        selected = []
        
        # Get random questions by difficulty
        easy_qs = list(qs.filter(difficulty="EASY").order_by('?')[:easy_count])
        medium_qs = list(qs.filter(difficulty="MEDIUM").order_by('?')[:medium_count])
        hard_qs = list(qs.filter(difficulty="HARD").order_by('?')[:hard_count])
        
        selected = easy_qs + medium_qs + hard_qs
        
        # Fill remaining if not enough in certain difficulties
        if len(selected) < count:
            remaining = list(
                qs.exclude(pk__in=[q.pk for q in selected])
                  .order_by('?')[:count - len(selected)]
            )
            selected.extend(remaining)
        
        logger.info(
            "Selected %d questions (Easy:%d, Medium:%d, Hard:%d) for company=%s",
            len(selected),
            len([q for q in selected if q.difficulty == "EASY"]),
            len([q for q in selected if q.difficulty == "MEDIUM"]),
            len([q for q in selected if q.difficulty == "HARD"]),
            company_slug,
        )
        
        return selected[:count]
    
    def evaluate_answer(
        self,
        interview_question: str,
        reference_answer: str,
        candidate_answer: str,
        question_type: str,
    ) -> dict:
        """Evaluate candidate's answer against reference."""
        return self.llm.evaluate_answer(
            interview_question=interview_question,
            reference_answer=reference_answer,
            candidate_answer=candidate_answer,
            question_type=question_type,
        )