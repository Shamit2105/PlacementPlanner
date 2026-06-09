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
from .tasks import evaluate_session_answers

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
        
        # Update session progress
        session.questions_answered = InterviewQuestion.objects.filter(
            session=session,
            status__in=[InterviewQuestion.QuestionStatus.ANSWERED, InterviewQuestion.QuestionStatus.EVALUATED],
        ).count()
        session.save()
        
        # Check if complete
        pending_count = InterviewQuestion.objects.filter(
            session=session,
            status=InterviewQuestion.QuestionStatus.PENDING,
        ).count()
        if pending_count == 0:
            session.status = InterviewSession.SessionStatus.COMPLETED
            session.completed_at = timezone.now()
            session.save()
            evaluate_session_answers.delay(session.id)
        
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
            # Check if session needs completion
            pending_count = InterviewQuestion.objects.filter(
                session=session,
                status=InterviewQuestion.QuestionStatus.PENDING,
            ).count()
            if pending_count == 0 and session.status == InterviewSession.SessionStatus.IN_PROGRESS:
                session.status = InterviewSession.SessionStatus.COMPLETED
                session.completed_at = timezone.now()
                session.save()
                evaluate_session_answers.delay(session.id)
                
            return Response(
                {"message": "Interview complete!", "session": InterviewSessionSerializer(session).data}
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
        
        # Check if complete
        pending_count = InterviewQuestion.objects.filter(
            session=session,
            status=InterviewQuestion.QuestionStatus.PENDING,
        ).count()
        if pending_count == 0:
            session.status = InterviewSession.SessionStatus.COMPLETED
            session.completed_at = timezone.now()
            session.save()
            evaluate_session_answers.delay(session.id)
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
            evaluate_session_answers.delay(session.id)
            
        return Response(InterviewSessionSerializer(session).data)