from django.db import models
from django.conf import settings
from companies.models import Question, Company, QuestionType, Difficulty


class InterviewSession(models.Model):
    """
    A single mock interview session.
    User picks company + question types → we serve questions → they answer → get feedback.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="interview_sessions",
    )
    company = models.ForeignKey(
        Company,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="interview_sessions",
    )
    
    # Session config
    total_questions = models.PositiveSmallIntegerField(default=5)
    questions_answered = models.PositiveSmallIntegerField(default=0)
    
    # Scoring
    total_score = models.FloatField(default=0.0)  # Average across all answers
    max_possible_score = models.FloatField(default=10.0)
    
    # Status
    class SessionStatus(models.TextChoices):
        IN_PROGRESS = "IN_PROGRESS", "In Progress"
        COMPLETED = "COMPLETED", "Completed"
        ABANDONED = "ABANDONED", "Abandoned"
    
    status = models.CharField(
        max_length=20,
        choices=SessionStatus.choices,
        default=SessionStatus.IN_PROGRESS,
    )
    
    # Which types to include
    question_types = models.JSONField(
        default=list,
        help_text="List of question types e.g. ['DSA_CODING', 'SYSTEM_DESIGN']"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ["-created_at"]
    
    def __str__(self):
        return f"Interview #{self.pk} - {self.user.email} ({self.company})"


class InterviewQuestion(models.Model):
    """
    A question served during an interview session.
    Stores the question, candidate's answer, and evaluation.
    """
    session = models.ForeignKey(
        InterviewSession,
        on_delete=models.CASCADE,
        related_name="interview_questions",
    )
    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name="interview_appearances",
    )
    
    # Order in the session
    order = models.PositiveSmallIntegerField()
    
    # Candidate's response
    candidate_answer = models.TextField(blank=True)
    
    # LLM Evaluation
    score = models.FloatField(null=True, blank=True)  # 0-10
    verdict = models.CharField(max_length=20, blank=True)  # Strong / Acceptable / Needs Work
    feedback = models.TextField(blank=True)
    strengths = models.JSONField(default=list, blank=True)
    improvements = models.JSONField(default=list, blank=True)
    missed_concepts = models.JSONField(default=list, blank=True)
    
    # Timing
    time_taken_seconds = models.PositiveIntegerField(null=True, blank=True)
    
    # Status
    class QuestionStatus(models.TextChoices):
        PENDING = "PENDING", "Pending"
        ANSWERED = "ANSWERED", "Answered"
        EVALUATED = "EVALUATED", "Evaluated"
        SKIPPED = "SKIPPED", "Skipped"
    
    status = models.CharField(
        max_length=20,
        choices=QuestionStatus.choices,
        default=QuestionStatus.PENDING,
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    evaluated_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ["session", "order"]
        unique_together = ["session", "order"]
    
    def __str__(self):
        return f"Q{self.order} - Session #{self.session_id}"