"""
Questions App — Models
========================
Central question bank. Every scraped or LLM-generated question lives here.

Entity relationship:
  Company ←M2M→ Question ←M2M→ Topic
  Question has a VectorField (768-dim Gemini embedding) for semantic search.

Pipeline states for a Question:
  SCRAPED → (Celery task) → PROCESSED → (embedding task) → EMBEDDED
  FAILED if any step errors out
"""

from django.db import models
from pgvector.django import VectorField    # pgvector Django integration


# ─── Choice Enums ─────────────────────────────────────────────────────────────

class QuestionType(models.TextChoices):
    """Category of interview question — drives scraping strategy and interview mix."""
    DSA_CODING    = "DSA_CODING",    "DSA Coding Problem"
    DSA_THEORY    = "DSA_THEORY",    "DSA Theory / Concept"
    OS            = "OS",            "Operating Systems"
    DBMS          = "DBMS",          "Database Management Systems"
    NETWORKS      = "NETWORKS",      "Computer Networks"
    SYSTEM_DESIGN = "SYSTEM_DESIGN", "System Design"


class Difficulty(models.TextChoices):
    EASY   = "EASY",   "Easy"
    MEDIUM = "MEDIUM", "Medium"
    HARD   = "HARD",   "Hard"


class QuestionSource(models.TextChoices):
    LEETCODE  = "LC",        "LeetCode"
    GFG       = "GFG",       "GeeksForGeeks"
    GENERATED = "GENERATED", "LLM Generated"  # when scraping yields nothing


class ProcessingStatus(models.TextChoices):
    """Tracks where in the pipeline each question is."""
    SCRAPED   = "SCRAPED",   "Scraped — raw text, not yet LLM-processed"
    PROCESSED = "PROCESSED", "LLM has formatted question + written answer"
    EMBEDDED  = "EMBEDDED",  "Embedding computed, ready for semantic search"
    FAILED    = "FAILED",    "Processing failed — see error_log"


# ─── Core Lookup Tables ───────────────────────────────────────────────────────

class Company(models.Model):
    """
    Companies that users can request interview prep for.
    Questions are tagged to companies so we can quickly fetch relevant sets.
    """
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
    """
    Fine-grained topic tags e.g. "Binary Search", "SQL Joins", "TCP/IP".
    These drive both Serper search queries and vector similarity lookups.
    """
    name = models.CharField(max_length=120, unique=True)
    # Parent category so UI can group topics by type
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
    """
    Stores the original scraped interview experience text once.
    Multiple Questions can reference the same source without duplication.
    """
    source_url = models.URLField(unique=True, help_text="Original scraped URL")
    raw_text = models.TextField(help_text="Full raw scraped content")
    company = models.CharField(max_length=200, blank=True, help_text="Company mentioned in the post")
    scraped_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-scraped_at"]
        verbose_name = "Raw Scraped Content"
        verbose_name_plural = "Raw Scraped Contents"

    def __str__(self):
        return f"Raw: {self.source_url[:80]}..."


# ─── Main Question Model ──────────────────────────────────────────────────────

class Question(models.Model):
    """
    The core entity: a single interview question with its reference answer.

    Two text representations:
      • question_text         — raw scraped/generated text (may be messy)
      • interview_question    — LLM-reformatted as a clean interview prompt
      • interview_answer      — LLM-written reference answer in interview style

    The embedding (VectorField) stores a 768-dim Gemini embedding of
    interview_question so we can do cosine-similarity search via pgvector.
    """

    # ── Question content ──────────────────────────────────────────────────────
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

    # ── Classification ────────────────────────────────────────────────────────
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

    # ── Provenance ────────────────────────────────────────────────────────────
    source = models.CharField(
        max_length=20,
        choices=QuestionSource.choices,
        default=QuestionSource.GFG,
    )
    source_url = models.URLField(blank=True, help_text="Original scraped URL if applicable.")

    # ── Relationships ─────────────────────────────────────────────────────────
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

    # ── Pipeline state ────────────────────────────────────────────────────────
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

    # ── pgvector embedding ────────────────────────────────────────────────────
    # WHY: stored embeddings let us find semantically similar questions
    # without re-calling Gemini on every search. Cosine distance in pgvector
    # is O(log n) with an IVFFlat index vs O(n) full scan.
    # 768 dims = Gemini embedding-001 / text-embedding-004 output size.
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
        help_text="Comma-separated topic tags auto-classified by LLM (e.g., 'binary-search,dynamic-programming')")

    # ── Audit / quality flags ─────────────────────────────────────────────────
    is_duplicate = models.BooleanField(
        default=False,
        help_text="Flagged true if cosine similarity > 0.95 to an existing question.",
    )
    times_used = models.PositiveIntegerField(
        default=0,
        help_text="How many mock interviews have included this question.",
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

    def __str__(self):
        preview = self.interview_question
        return f"[{self.question_type}] {preview[:80]}..."
