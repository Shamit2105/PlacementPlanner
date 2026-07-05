from django.db import models
from pgvector.django import VectorField  # pgvector Django integration


class QuestionType(models.TextChoices):
    DSA_CODING = "DSA_CODING", "DSA Coding Problem"
    DSA_THEORY = "DSA_THEORY", "DSA Theory / Concept"
    OS = "OS", "Operating Systems"
    DBMS = "DBMS", "Database Management Systems"
    NETWORKS = "NETWORKS", "Computer Networks"
    SYSTEM_DESIGN = "SYSTEM_DESIGN", "System Design"


class Difficulty(models.TextChoices):
    EASY = "EASY", "Easy"
    MEDIUM = "MEDIUM", "Medium"
    HARD = "HARD", "Hard"


class QuestionSource(models.TextChoices):
    LEETCODE = "LC", "LeetCode"
    GFG = "GFG", "GeeksForGeeks"
    GENERATED = "GENERATED", "LLM Generated"  # when scraping yields nothing


class ProcessingStatus(models.TextChoices):
    SCRAPED = "SCRAPED", "Scraped — raw text, not yet LLM-processed"
    PROCESSED = "PROCESSED", "LLM has formatted question + written answer"
    EMBEDDED = "EMBEDDED", "Embedding computed, ready for semantic search"
    FAILED = "FAILED", "Processing failed — see error_log"


class Company(models.Model):
    name = models.CharField(max_length=120, unique=True)
    # Normalized slug for Serper search queries e.g. "google", "amazon"
    slug = models.SlugField(max_length=120, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "Companies"

    def __str__(self):
        return self.name


class Topic(models.Model):
    name = models.CharField(max_length=120, unique=True)
    question_type = models.CharField(
        max_length=20,
        choices=QuestionType.choices,
        db_index=True,
    )

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.question_type})"


class RawScrapedContent(models.Model):
    source_url = models.URLField(unique=True, help_text="Original scraped URL")
    raw_text = models.TextField(help_text="Full raw scraped content")
    company = models.CharField(
        max_length=200, blank=True, help_text="Company mentioned in the post"
    )
    scraped_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-scraped_at"]
        verbose_name = "Raw Scraped Content"
        verbose_name_plural = "Raw Scraped Contents"

    def __str__(self):
        return f"Raw: {self.source_url[:80]}..."


class Question(models.Model):
    raw_source = models.ForeignKey(
        RawScrapedContent,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="questions",
        help_text="Link to original scraped content. Null for LLM-generated questions.",
    )
    interview_question = models.TextField(
        blank=True,
        help_text="LLM-cleaned version phrased as an interviewer would ask it.",
    )
    interview_answer = models.TextField(
        blank=True,
        help_text="LLM-written reference answer in conversational interview style.",
    )

    question_type = models.CharField(
        max_length=20,
        choices=QuestionType.choices,
        db_index=True,
    )
    difficulty = models.CharField(
        max_length=10,
        choices=Difficulty.choices,
        default=Difficulty.MEDIUM,
    )

    source = models.CharField(
        max_length=20,
        choices=QuestionSource.choices,
        default=QuestionSource.GFG,
    )
    source_url = models.URLField(
        blank=True, help_text="Original scraped URL if applicable."
    )

    companies = models.ManyToManyField(
        Company,
        blank=True,
        related_name="questions",
        help_text="Companies this question has been asked at.",
    )
    topics = models.ManyToManyField(
        Topic,
        blank=True,
        related_name="questions",
        help_text="Fine-grained topic tags e.g. 'Binary Search', 'SQL Joins'.",
    )

    status = models.CharField(
        max_length=20,
        choices=ProcessingStatus.choices,
        default=ProcessingStatus.SCRAPED,
        db_index=True,
    )
    error_log = models.TextField(
        blank=True,
        help_text="Captured exception text if LLM/embedding step failed.",
    )

    embedding = VectorField(
        dimensions=384,
        null=True,
        blank=True,
        help_text="384-dim HF embedding for semantic similarity search.",
    )

    topic_tags = models.CharField(
        max_length=500,
        blank=True,
        default="",
        help_text="Comma-separated topic tags auto-classified by LLM (e.g., 'binary-search,dynamic-programming')",
    )

    is_duplicate = models.BooleanField(
        default=False,
        help_text="Flagged true if cosine similarity > 0.95 to an existing question.",
    )
    times_used = models.PositiveIntegerField(
        default=0,
        help_text="How many mock interviews have included this question.",
    )

    evaluation_rubric = models.JSONField(
        default=dict,
        blank=True,
        help_text="Structured rubric used for answer evaluation.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["question_type", "status"]),
            models.Index(fields=["source", "status"]),
            models.Index(fields=["is_duplicate"]),
        ]

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.topic_tags:
            tags = [t.strip() for t in self.topic_tags.split(",") if t.strip()]
            for tag in tags:
                topic = Topic.objects.filter(name__iexact=tag).first()
                if not topic:
                    try:
                        topic, _ = Topic.objects.get_or_create(
                            name=tag, defaults={"question_type": self.question_type}
                        )
                    except Exception:
                        topic = Topic.objects.filter(name__iexact=tag).first()
                if topic:
                    self.topics.add(topic)

    def __str__(self):
        preview = self.interview_question
        return f"[{self.question_type}] {preview[:80]}..."
