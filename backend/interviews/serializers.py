from rest_framework import serializers
from .models import InterviewSession, InterviewQuestion
from companies.models import Company


class InterviewQuestionSerializer(serializers.ModelSerializer):
    question_id = serializers.IntegerField(source="question.id", read_only=True)
    question_text = serializers.CharField(source="question.interview_question", read_only=True)
    question_type = serializers.CharField(source="question.question_type", read_only=True)
    difficulty = serializers.CharField(source="question.difficulty", read_only=True)
    topic_tags = serializers.CharField(source="question.topic_tags", read_only=True)
    reference_answer = serializers.CharField(source="question.interview_answer", read_only=True)
    
    class Meta:
        model = InterviewQuestion
        fields = [
            "id", "question_id", "order", "question_text", "question_type", "difficulty",
            "topic_tags", "reference_answer", "candidate_answer",
            "score", "verdict", "feedback", "strengths", "improvements",
            "missed_concepts", "status", "evaluated_at",
        ]
        read_only_fields = [
            "score", "verdict", "feedback", "strengths", "improvements",
            "missed_concepts", "evaluated_at",
        ]


class InterviewSessionSerializer(serializers.ModelSerializer):
    questions = InterviewQuestionSerializer(source="interview_questions", many=True, read_only=True)
    company_name = serializers.CharField(source="company.name", read_only=True)
    
    class Meta:
        model = InterviewSession
        fields = [
            "id", "company", "company_name", "total_questions",
            "questions_answered", "total_score", "max_possible_score",
            "status", "question_types", "questions",
            "created_at", "completed_at",
        ]
        read_only_fields = [
            "questions_answered", "total_score", "status",
            "created_at", "completed_at",
        ]


class StartInterviewSerializer(serializers.Serializer):
    company_slug = serializers.CharField(required=False, allow_blank=True)
    question_types = serializers.ListField(
        child=serializers.CharField(),
        default=["DSA_CODING"],
    )
    total_questions = serializers.IntegerField(default=5, min_value=1, max_value=20)


class SubmitAnswerSerializer(serializers.Serializer):
    question_order = serializers.IntegerField(min_value=1)
    candidate_answer = serializers.CharField()
