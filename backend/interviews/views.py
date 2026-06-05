from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.utils import timezone

from .models import InterviewSession, InterviewQuestion
from .serializers import (
    InterviewSessionSerializer,
    InterviewQuestionSerializer,
    StartInterviewSerializer,
    SubmitAnswerSerializer,
)
from .services import InterviewService


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
        
        # Select questions
        service = InterviewService()
        questions = service.select_questions(
            company_slug=data.get("company_slug", ""),
            question_types=session.question_types,
            count=session.total_questions,
        )
        
        # Create interview questions
        for i, question in enumerate(questions, 1):
            InterviewQuestion.objects.create(
                session=session,
                question=question,
                order=i,
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
        
        # Evaluate
        service = InterviewService()
        evaluation = service.evaluate_answer(
            interview_question=interview_q.question.interview_question,
            reference_answer=interview_q.question.interview_answer,
            candidate_answer=data["candidate_answer"],
            question_type=interview_q.question.question_type,
        )
        
        # Save evaluation
        interview_q.score = evaluation.get("score")
        interview_q.verdict = evaluation.get("verdict")
        interview_q.feedback = evaluation.get("feedback")
        interview_q.strengths = evaluation.get("strengths", [])
        interview_q.improvements = evaluation.get("improvements", [])
        interview_q.missed_concepts = evaluation.get("missed_concepts", [])
        interview_q.status = InterviewQuestion.QuestionStatus.EVALUATED
        interview_q.evaluated_at = timezone.now()
        interview_q.save()
        
        # Update session progress
        session.questions_answered = InterviewQuestion.objects.filter(
            session=session,
            status=InterviewQuestion.QuestionStatus.EVALUATED,
        ).count()
        
        # Calculate average score
        scores = InterviewQuestion.objects.filter(
            session=session,
            score__isnull=False,
        ).values_list("score", flat=True)
        
        if scores:
            session.total_score = sum(scores) / len(scores)
        
        # Check if complete
        if session.questions_answered >= session.total_questions:
            session.status = InterviewSession.SessionStatus.COMPLETED
            session.completed_at = timezone.now()
        
        session.save()
        
        return Response(InterviewQuestionSerializer(interview_q).data)
    
    @action(detail=True, methods=["get"])
    def next_question(self, request, pk=None):
        """Get the next unanswered question."""
        session = self.get_object()
        
        next_q = InterviewQuestion.objects.filter(
            session=session,
            status=InterviewQuestion.QuestionStatus.PENDING,
        ).order_by("order").first()
        
        if not next_q:
            # Check if session is complete
            if session.questions_answered >= session.total_questions:
                return Response(
                    {"message": "Interview complete!", "session": InterviewSessionSerializer(session).data}
                )
            return Response(
                {"message": "No pending questions found"},
                status=status.HTTP_404_NOT_FOUND,
            )
        
        return Response(InterviewQuestionSerializer(next_q).data)