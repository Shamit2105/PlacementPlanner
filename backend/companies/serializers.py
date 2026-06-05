"""
Questions App — Serializers
=============================
DRF serializers handle:
  • Serializing Question / Company / Topic queryset → JSON response
  • Validating incoming data for write operations

Design notes:
  • embedding field is EXCLUDED from all serializers (768 floats = ~6KB per question)
    Use the dedicated /api/v1/questions/semantic-search/ endpoint instead.
  • question_text (raw scraped) is hidden from list endpoints — clients
    only need interview_question (clean) and interview_answer (formatted).
"""

from rest_framework import serializers
from .models import Question, Company, Topic, QuestionType, Difficulty

from .tasks import process_single_question


class CompanySerializer(serializers.ModelSerializer):
    class Meta:
        model   = Company
        fields  = ["id", "name", "slug", "created_at"]
        read_only_fields = ["id", "created_at"]


class TopicSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Topic
        fields = ["id", "name", "question_type"]
        read_only_fields = ["id"]


class QuestionListSerializer(serializers.ModelSerializer):
    """
    Compact representation for list endpoints.
    Does NOT include the full interview_answer (could be 500+ words).
    Shows a 200-char preview of the answer instead.
    """
    companies         = CompanySerializer(many=True, read_only=True)
    topics            = TopicSerializer(many=True, read_only=True)
    answer_preview    = serializers.SerializerMethodField()
    question_type_display = serializers.CharField(
        source="get_question_type_display", read_only=True
    )
    difficulty_display = serializers.CharField(
        source="get_difficulty_display", read_only=True
    )

    class Meta:
        model  = Question
        fields = [
            "id",
            "interview_question",
            "answer_preview",
            "question_type",
            "question_type_display",
            "difficulty",
            "difficulty_display",
            "source",
            "source_url",
            "status",
            "is_duplicate",
            "times_used",
            "companies",
            "topics",
            "created_at",
        ]

    def get_answer_preview(self, obj: Question) -> str:
        """Return first 200 chars of the answer for list views."""
        return obj.interview_answer[:200] + "..." if len(obj.interview_answer) > 200 else obj.interview_answer


class QuestionDetailSerializer(serializers.ModelSerializer):
    """
    Full question detail including the complete reference answer.
    Used for /questions/<id>/ and in interview result views.
    """
    companies = CompanySerializer(many=True, read_only=True)
    topics    = TopicSerializer(many=True, read_only=True)
    question_type_display = serializers.CharField(
        source="get_question_type_display", read_only=True
    )
    difficulty_display = serializers.CharField(
        source="get_difficulty_display", read_only=True
    )

    class Meta:
        model  = Question
        fields = [
            "id",       # raw scraped (for admin transparency)
            "interview_question",    # LLM-cleaned
            "interview_answer",      # LLM reference answer — FULL text
            "question_type",
            "question_type_display",
            "difficulty",
            "difficulty_display",
            "source",
            "source_url",
            "status",
            "error_log",
            "is_duplicate",
            "times_used",
            "companies",
            "topics",
            "created_at",
            "updated_at",
        ]
        # embedding excluded — use semantic search endpoint


class QuestionCreateSerializer(serializers.ModelSerializer):
    """
    For manually adding questions (admin / test data seeding).
    Only raw fields — LLM formatting is triggered as a background task.
    """
    company_slugs = serializers.ListField(
        child=serializers.SlugField(),
        write_only=True,
        required=False,
        help_text="List of company slugs to associate (e.g. ['google', 'amazon'])",
    )
    topic_ids = serializers.PrimaryKeyRelatedField(
        queryset=Topic.objects.all(),
        many=True,
        write_only=True,
        required=False,
    )

    class Meta:
        model  = Question
        fields = [
            "question_type",
            "difficulty",
            "source",
            "source_url",
            "company_slugs",
            "topic_ids",
        ]

    def create(self, validated_data):
        company_slugs = validated_data.pop("company_slugs", [])
        topic_ids     = validated_data.pop("topic_ids", [])
        question      = Question.objects.create(**validated_data)

        for slug in company_slugs:
            company, _ = Company.objects.get_or_create(
                slug=slug,
                defaults={"name": slug.replace("-", " ").title()},
            )
            question.companies.add(company)

        if topic_ids:
            question.topics.set(topic_ids)

        # Trigger background LLM processing
        
        process_single_question.delay(question.pk)

        return question


class SemanticSearchSerializer(serializers.Serializer):
    """
    Input validation for the semantic search endpoint.
    The user provides a text query; we embed it and search pgvector.
    """
    query         = serializers.CharField(min_length=3, max_length=500)
    question_type = serializers.ChoiceField(
        choices=QuestionType.choices,
        required=False,
        allow_blank=True,
    )
    company_slug = serializers.SlugField(required=False, allow_blank=True)
    limit        = serializers.IntegerField(min_value=1, max_value=50, default=10)


class ScrapeRequestSerializer(serializers.Serializer):
    """
    Input for the /questions/scrape/ endpoint.
    Triggers the scrape_and_ingest_questions Celery task.
    """
    question_type = serializers.ChoiceField(choices=QuestionType.choices)
    company_name  = serializers.CharField(max_length=120, required=False, allow_blank=True)
    topic_name    = serializers.CharField(max_length=120, required=False, allow_blank=True)
    target_count  = serializers.IntegerField(min_value=1, max_value=50, default=10)
