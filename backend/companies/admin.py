"""
Questions App — Django Admin
"""

from django.contrib import admin
from django.utils.html import format_html


from .tasks import compute_and_store_embedding,process_single_question
from .models import Company, Topic, Question, ProcessingStatus


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display  = ["name", "slug", "question_count", "created_at"]
    search_fields = ["name", "slug"]
    prepopulated_fields = {"slug": ["name"]}

    def question_count(self, obj):
        return obj.questions.count()
    question_count.short_description = "# Questions"


@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    list_display  = ["name", "question_type", "question_count"]
    list_filter   = ["question_type"]
    search_fields = ["name"]

    def question_count(self, obj):
        return obj.questions.count()
    question_count.short_description = "# Questions"


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display  = [
        "short_question", "question_type", "difficulty", "source",
        "status", "is_duplicate", "times_used", "has_embedding", "created_at",
    ]
    list_filter   = ["question_type", "difficulty", "source", "status", "is_duplicate"]
    search_fields = ["interview_question", "question_text"]
    filter_horizontal = ["companies", "topics"]
    readonly_fields = [
        "status", "is_duplicate", "times_used", "created_at", "updated_at",
        "error_log", "source_url",
    ]

    # Action to retry LLM processing for failed questions
    actions = ["retry_processing", "recompute_embeddings", "mark_as_not_duplicate"]

    fieldsets = [
        ("Content", {
            "fields": ["question_text", "interview_question", "interview_answer"],
        }),
        ("Classification", {
            "fields": ["question_type", "difficulty", "source", "source_url"],
        }),
        ("Relationships", {
            "fields": ["companies", "topics"],
        }),
        ("Pipeline State", {
            "fields": ["status", "error_log", "is_duplicate", "times_used"],
            "classes": ["collapse"],
        }),
        ("Timestamps", {
            "fields": ["created_at", "updated_at"],
            "classes": ["collapse"],
        }),
    ]

    def short_question(self, obj):
        text = obj.interview_question or obj.question_text
        return text[:60] + "..." if len(text) > 60 else text
    short_question.short_description = "Question"

    def has_embedding(self, obj):
        if obj.embedding is not None:
            return format_html('<span style="color:green">✓</span>')
        return format_html('<span style="color:red">✗</span>')
    has_embedding.short_description = "Embedded"

    @admin.action(description="Retry LLM processing for selected questions")
    def retry_processing(self, request, queryset):
        count = 0
        for q in queryset.filter(status__in=[ProcessingStatus.FAILED, ProcessingStatus.SCRAPED]):
            process_single_question.delay(q.pk)
            count += 1
        self.message_user(request, f"Queued {count} questions for reprocessing.")

    @admin.action(description="Recompute embeddings for selected questions")
    def recompute_embeddings(self, request, queryset):
        count = 0
        for q in queryset.filter(status=ProcessingStatus.PROCESSED):
            compute_and_store_embedding.delay(q.pk)
            count += 1
        self.message_user(request, f"Queued {count} embedding computations.")

    @admin.action(description="Mark selected as NOT duplicate")
    def mark_as_not_duplicate(self, request, queryset):
        updated = queryset.update(is_duplicate=False)
        self.message_user(request, f"Cleared duplicate flag on {updated} questions.")
