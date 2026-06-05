"""
Questions App — Filters
========================
DjangoFilterBackend filter class for the QuestionListView.
Allows filtering by type, difficulty, company, topic, source, status.
"""
import django_filters
from django_filters import rest_framework as filters

from .models import Question, Company, Topic, QuestionType, Difficulty, QuestionSource, ProcessingStatus


class QuestionFilter(django_filters.FilterSet):
    """
    Filter questions by multiple attributes simultaneously.

    Example: GET /api/v1/questions/?question_type=DSA_CODING&company=google&difficulty=HARD
    """

    # Exact match on choice fields
    question_type = filters.ChoiceFilter(choices=QuestionType.choices)
    difficulty    = filters.ChoiceFilter(choices=Difficulty.choices)
    source        = filters.ChoiceFilter(choices=QuestionSource.choices)
    status        = filters.ChoiceFilter(choices=ProcessingStatus.choices)
    is_duplicate  = filters.BooleanFilter()

    # Related model filters — filter by company slug or topic name
    company = filters.CharFilter(
        field_name="companies__slug",
        lookup_expr="iexact",
        label="Company (slug)",
    )
    topic = filters.ModelChoiceFilter(
        field_name="topics__id",
        queryset=Topic.objects.all(),
        label="Topic (id)",
    )

    # Range filter for times_used (e.g. find popular questions)
    min_times_used = filters.NumberFilter(field_name="times_used", lookup_expr="gte")
    max_times_used = filters.NumberFilter(field_name="times_used", lookup_expr="lte")

    class Meta:
        model  = Question
        fields = [
            "question_type",
            "difficulty",
            "source",
            "status",
            "is_duplicate",
            "company",
            "topic",
        ]
