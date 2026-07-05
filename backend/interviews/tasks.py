import logging

from celery import shared_task
from companies.llm_service import LLMService
from django.utils import timezone

from .models import InterviewQuestion, InterviewSession
from .services import normalize_verdict

logger = logging.getLogger(__name__)


@shared_task(name="interviews.evaluate_session_answers")
def evaluate_session_answers(session_id: int):
    try:
        session = InterviewSession.objects.get(pk=session_id)
    except InterviewSession.DoesNotExist:
        return

    # Find all answered questions that haven't been evaluated
    answered_questions = InterviewQuestion.objects.filter(
        session=session, status=InterviewQuestion.QuestionStatus.ANSWERED
    )

    if not answered_questions.exists():
        return

    llm = LLMService()

    for iq in answered_questions:
        q = iq.question

        # 1. Ensure the underlying question has a reference answer
        if not q.interview_answer:
            logger.info(f"Generating missing reference answer for Question {q.pk}")
            try:
                ans = llm.generate_answer(q.interview_question, q.question_type)
                q.interview_answer = ans
                q.save(update_fields=["interview_answer"])
            except Exception as e:
                logger.error(f"Failed to generate answer for Question {q.pk}: {e}")
                # We can't evaluate without a reference answer
                continue

        # 2. Evaluate the candidate's answer
        try:
            logger.info(f"Evaluating InterviewQuestion {iq.pk}")
            evaluation = llm.evaluate_answer(
                question=q.interview_question,
                rubric=q.evaluation_rubric,
                candidate_answer=iq.candidate_answer,
                question_type=q.question_type,
            )
            evaluation["verdict"] = normalize_verdict(
                evaluation.get("verdict"), evaluation.get("score")
            )

            # Save evaluation
            iq.score = evaluation.get("score")
            iq.verdict = evaluation.get("verdict")
            iq.feedback = evaluation.get("feedback")
            iq.strengths = evaluation.get("strengths", [])
            iq.improvements = evaluation.get("improvements", [])
            iq.missed_concepts = evaluation.get("missed_concepts", [])
            iq.status = InterviewQuestion.QuestionStatus.EVALUATED
            iq.evaluated_at = timezone.now()
            iq.save()

        except Exception as e:
            logger.error(f"Failed to evaluate InterviewQuestion {iq.pk}: {e}")

    # 3. Update session scores
    # Recalculate average score
    scores = InterviewQuestion.objects.filter(
        session=session,
        score__isnull=False,
    ).values_list("score", flat=True)

    if scores:
        session.total_score = sum(scores) / len(scores)

    # Update questions_answered
    session.questions_answered = InterviewQuestion.objects.filter(
        session=session,
        status__in=[
            InterviewQuestion.QuestionStatus.ANSWERED,
            InterviewQuestion.QuestionStatus.EVALUATED,
        ],
    ).count()

    session.save(update_fields=["total_score", "questions_answered"])
    logger.info(f"Completed evaluation for session {session_id}")
