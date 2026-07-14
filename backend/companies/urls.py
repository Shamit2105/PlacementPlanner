"""
Questions App — URL Configuration
"""

from django.urls import path
from . import views

app_name = "questions"

urlpatterns = [
    # ── Company and Topic management ──────────────────────────────────────────
    path("companies/", views.CompanyListCreateView.as_view(), name="company-list"),
    path("topics/", views.TopicListCreateView.as_view(), name="topic-list"),

    # ── Question bank CRUD ────────────────────────────────────────────────────
    path("", views.QuestionListCreateView.as_view(), name="question-list"),
    path("<int:pk>/", views.QuestionDetailView.as_view(), name="question-detail"),
    path("<int:pk>/generate-answer/", views.GenerateAnswerView.as_view(), name="generate-answer"),
    path("<int:pk>/similar/", views.SimilarQuestionsView.as_view(), name="similar-questions"),
    path("<int:pk>/delete",views.QuestionDetailView.as_view(),name="question-delete"),
    # ── Vector / Semantic ─────────────────────────────────────────────────────
    path("semantic-search/", views.SemanticSearchView.as_view(), name="semantic-search"),

    # ── Admin / Operations ────────────────────────────────────────────────────
    path("scrape/", views.TriggerScrapeView.as_view(), name="trigger-scrape"),
    path("stats/", views.question_bank_stats, name="stats"),

    # ── Task polling (shared with interviews app) ─────────────────────────────
    path("tasks/<str:task_id>/status/", views.task_status_view, name="task-status"),
]
