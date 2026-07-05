import logging

from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import InterviewQuestion, InterviewSession
from .serializers import (
    InterviewQuestionSerializer,
    InterviewSessionSerializer,
    StartInterviewSerializer,
    SubmitAnswerSerializer,
)
from .services import InterviewService
from .tasks import evaluate_session_answers

logger = logging.getLogger(__name__)


class InterviewSessionViewSet(viewsets.ModelViewSet):
    """CRUD for interview sessions."""

    serializer_class = InterviewSessionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return InterviewSession.objects.filter(user=self.request.user)

    @action(detail=False, methods=["post"])
    def start(self, request):
        """
        Start a new interview session.

        POST /api/interviews/start/
        {
            "company_slug": "amazon",
            "question_types": ["DSA_CODING", "SYSTEM_DESIGN"],
            "total_questions": 5
        }
        """
        serializer = StartInterviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data

        # Create session
        session = InterviewSession.objects.create(
            user=request.user,
            company_id=data.get("company_id"),
            total_questions=data.get("total_questions", 5),
            question_types=data.get("question_types", ["DSA_CODING"]),
        )

        # Select the first EASY question to start the interview
        service = InterviewService()
        questions = service.select_questions(
            company_slug=data.get("company_slug", ""),
            question_types=session.question_types,
            count=1,
            difficulty="EASY",
            user=request.user,
        )

        # Create the initial interview question with order 1
        if questions:
            InterviewQuestion.objects.create(
                session=session,
                question=questions[0],
                order=1,
            )

        return Response(
            InterviewSessionSerializer(session).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"])
    def submit_answer(self, request, pk=None):
        """
        Submit answer for a question.

        POST /api/interviews/{session_id}/submit_answer/
        {
            "question_order": 1,
            "candidate_answer": "I would use a hash map to..."
        }
        """
        session = self.get_object()

        serializer = SubmitAnswerSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data

        interview_q = get_object_or_404(
            InterviewQuestion,
            session=session,
            order=data["question_order"],
        )

        # Save answer
        interview_q.candidate_answer = data["candidate_answer"]
        interview_q.status = InterviewQuestion.QuestionStatus.ANSWERED
        interview_q.save()

        # Immediate evaluation of the answer
        service = InterviewService()
        evaluation = service.evaluate_answer(
            interview_question=interview_q.question.interview_question,
            evaluation_rubric=interview_q.question.evaluation_rubric,
            candidate_answer=interview_q.candidate_answer,
            question_type=interview_q.question.question_type,
        )
        # Update interview question with evaluation results
        interview_q.score = evaluation.get("score")
        interview_q.verdict = evaluation.get("verdict")
        interview_q.feedback = evaluation.get("feedback")
        interview_q.strengths = evaluation.get("strengths", [])
        interview_q.improvements = evaluation.get("improvements", [])
        interview_q.missed_concepts = evaluation.get("missed_concepts", [])
        interview_q.status = InterviewQuestion.QuestionStatus.EVALUATED
        interview_q.save()

        # Update user profile with question stats
        if hasattr(request.user, "profile"):
            request.user.profile.questions_attempted.add(interview_q.question)
            if interview_q.score is not None and interview_q.score >= 7:
                request.user.profile.questions_passed.add(interview_q.question)
            else:
                request.user.profile.questions_failed.add(interview_q.question)

        # Determine next difficulty based on score (simple threshold)
        current_difficulty = (
            interview_q.question.difficulty.upper()
            if hasattr(interview_q.question, "difficulty")
            else None
        )
        next_difficulty = current_difficulty
        if interview_q.score is not None:
            if interview_q.score >= 7:
                # Progress to higher difficulty if possible
                if current_difficulty == "EASY":
                    next_difficulty = "MEDIUM"
                elif current_difficulty == "MEDIUM":
                    next_difficulty = "HARD"
                else:
                    next_difficulty = "HARD"
            else:
                # If low score, stay on same difficulty or focus on topic (e.g., OS)
                next_difficulty = current_difficulty

        # Check current count of created questions
        created_count = InterviewQuestion.objects.filter(session=session).count()

        if created_count < session.total_questions:
            # Create next question with adaptive difficulty
            next_order = interview_q.order + 1
            existing_q_ids = list(
                InterviewQuestion.objects.filter(session=session).values_list(
                    "question_id", flat=True
                )
            )
            next_qs = service.select_questions(
                company_slug=session.company.slug
                if hasattr(session, "company") and session.company
                else "",
                question_types=session.question_types,
                count=1,
                difficulty=next_difficulty,
                exclude_ids=existing_q_ids,
                user=request.user,
            )
            if next_qs:
                InterviewQuestion.objects.create(
                    session=session,
                    question=next_qs[0],
                    order=next_order,
                )
        else:
            # All questions generated, check if session is complete
            pending_count = InterviewQuestion.objects.filter(
                session=session,
                status=InterviewQuestion.QuestionStatus.PENDING,
            ).count()
            if pending_count == 0:
                session.status = InterviewSession.SessionStatus.COMPLETED
                session.completed_at = timezone.now()
                session.save()
                try:
                    evaluate_session_answers.delay(session.id)
                except Exception as e:
                    logger.error(
                        f"Failed to trigger evaluation task for session {session.id}: {e}"
                    )

        return Response(InterviewQuestionSerializer(interview_q).data)

    @action(detail=True, methods=["get"])
    def next_question(self, request, pk=None):
        """Get the next unanswered question."""
        session = self.get_object()

        next_q = (
            InterviewQuestion.objects.filter(
                session=session,
                status=InterviewQuestion.QuestionStatus.PENDING,
            )
            .order_by("order")
            .first()
        )

        if not next_q:
            # Check if session needs completion
            pending_count = InterviewQuestion.objects.filter(
                session=session,
                status=InterviewQuestion.QuestionStatus.PENDING,
            ).count()
            if (
                pending_count == 0
                and session.status == InterviewSession.SessionStatus.IN_PROGRESS
            ):
                session.status = InterviewSession.SessionStatus.COMPLETED
                session.completed_at = timezone.now()
                session.save()
                try:
                    evaluate_session_answers.delay(session.id)
                except Exception as e:
                    logger.error(
                        f"Failed to trigger evaluation task for session {session.id}: {e}"
                    )

            return Response(
                {
                    "message": "Interview complete!",
                    "session": InterviewSessionSerializer(session).data,
                }
            )

        return Response(InterviewQuestionSerializer(next_q).data)

    @action(detail=True, methods=["post"])
    def skip_question(self, request, pk=None):
        """
        Skip a question.

        POST /api/interviews/{session_id}/skip_question/
        {
            "question_order": 1
        }
        """
        session = self.get_object()
        question_order = request.data.get("question_order")
        if not question_order:
            return Response(
                {"error": "question_order is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        interview_q = get_object_or_404(
            InterviewQuestion,
            session=session,
            order=question_order,
        )

        if interview_q.status != InterviewQuestion.QuestionStatus.PENDING:
            return Response(
                {"error": "Only pending questions can be skipped"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        interview_q.status = InterviewQuestion.QuestionStatus.SKIPPED
        interview_q.save()

        # Check current count of created questions
        created_count = InterviewQuestion.objects.filter(session=session).count()

        if created_count < session.total_questions:
            # Create next question with the same difficulty
            service = InterviewService()
            next_order = interview_q.order + 1
            existing_q_ids = list(
                InterviewQuestion.objects.filter(session=session).values_list(
                    "question_id", flat=True
                )
            )
            current_difficulty = (
                interview_q.question.difficulty.upper()
                if hasattr(interview_q.question, "difficulty")
                else "EASY"
            )

            next_qs = service.select_questions(
                company_slug=session.company.slug
                if hasattr(session, "company") and session.company
                else "",
                question_types=session.question_types,
                count=1,
                difficulty=current_difficulty,
                exclude_ids=existing_q_ids,
                user=request.user,
            )
            if next_qs:
                InterviewQuestion.objects.create(
                    session=session,
                    question=next_qs[0],
                    order=next_order,
                )
        else:
            # All questions generated, check if session is complete
            pending_count = InterviewQuestion.objects.filter(
                session=session,
                status=InterviewQuestion.QuestionStatus.PENDING,
            ).count()
            if pending_count == 0:
                session.status = InterviewSession.SessionStatus.COMPLETED
                session.completed_at = timezone.now()
                session.save()
                try:
                    evaluate_session_answers.delay(session.id)
                except Exception as e:
                    logger.error(
                        f"Failed to trigger evaluation task for session {session.id}: {e}"
                    )
            else:
                session.save()

        return Response(InterviewQuestionSerializer(interview_q).data)

    @action(detail=True, methods=["post"])
    def end_session(self, request, pk=None):
        """
        End the interview session early.

        POST /api/interviews/{session_id}/end_session/
        """
        session = self.get_object()
        if session.status == InterviewSession.SessionStatus.IN_PROGRESS:
            session.status = InterviewSession.SessionStatus.COMPLETED
            session.completed_at = timezone.now()

            # Mark remaining pending questions as SKIPPED
            InterviewQuestion.objects.filter(
                session=session,
                status=InterviewQuestion.QuestionStatus.PENDING,
            ).update(status=InterviewQuestion.QuestionStatus.SKIPPED)

            session.save()
            try:
                evaluate_session_answers.delay(session.id)
            except Exception as e:
                logger.error(
                    f"Failed to trigger evaluation task for session {session.id}: {e}"
                )

        return Response(InterviewSessionSerializer(session).data)
