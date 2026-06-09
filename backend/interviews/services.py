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
            
        selected = list(qs.order_by('?')[:count])
        
        if len(selected) < count:
            shortfall = count - len(selected)
            logger.info(f"Not enough questions in DB (found {len(selected)}, need {count}). Generating {shortfall} new questions...")
            
            existing_texts = list(qs.values_list("interview_question", flat=True)[:50])
            import random
            from companies.models import QuestionSource
            
            for i in range(shortfall):
                qtype = random.choice(question_types)
                try:
                    result = self.llm.generate_unique_question(
                        question_type=qtype,
                        company=company_slug.replace('-', ' ') if company_slug else "",
                        topic="",
                        existing_questions=existing_texts,
                    )
                    
                    q = Question.objects.create(
                        raw_source=None,
                        interview_question=result.get("question", ""),
                        interview_answer=result.get("answer", ""),
                        question_type=qtype,
                        difficulty=result.get("difficulty", "Medium").upper() if result.get("difficulty") else "MEDIUM",
                        source=QuestionSource.GENERATED,
                        status=ProcessingStatus.PROCESSED,
                        topic_tags=",".join(result.get("topic_tags", [])) if result.get("topic_tags") else "",
                    )
                    
                    if company_slug:
                        company_obj = Company.objects.filter(slug=company_slug).first()
                        if company_obj:
                            q.companies.add(company_obj)
                            
                    selected.append(q)
                    existing_texts.append(result.get("question", ""))
                    logger.info(f"Generated new question: {q.pk}")
                except Exception as e:
                    logger.error(f"Failed to generate unique question: {e}")
                    
        for q in selected:
            if not q.interview_answer:
                logger.info(f"Generating missing reference answer for Question {q.pk} before starting interview...")
                try:
                    ans = self.llm.generate_answer(q.interview_question, q.question_type)
                    q.interview_answer = ans
                    q.save(update_fields=["interview_answer"])
                except Exception as e:
                    logger.error(f"Failed to generate answer for Question {q.pk}: {e}")
        
        import random
        random.shuffle(selected)
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