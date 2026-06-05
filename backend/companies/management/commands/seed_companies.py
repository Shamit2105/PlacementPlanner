"""
Management Command: seed_question_bank
=======================================
Usage:
  python manage.py seed_question_bank
  python manage.py seed_question_bank --company Google
  python manage.py seed_question_bank --all-companies

WHY this command?
  On first deploy, the question bank is empty. Before users can take
  interviews, we need to pre-populate it. This command triggers scraping
  tasks that download interview experience posts and let the LLM extract
  all questions with their auto-classified types and topics.

  It's idempotent — safe to run multiple times (scraper deduplicates).

CHANGES from old approach:
  --- CHANGE (WHAT): No longer scrape topic-by-topic. ---
  --- CHANGE (WHY): New pipeline scrapes full interview experiences and LLM 
  extracts ALL questions with auto-classified types. One experience post 
  contains DSA, System Design, DBMS questions all mixed together — exactly 
  what happens in real interviews. ---
  
  --- CHANGE (WHAT): One scraping task per company, not per topic×company. ---
  --- CHANGE (WHY): Experience posts naturally contain multiple topics.
  We let the LLM extract and classify everything from each post. ---
  
  --- CHANGE (WHAT): Topic records still created for filtering/search. ---
  --- CHANGE (WHY): Even though we don't scrape by topic, we still need 
  Topic records so users can filter questions by topic later. The LLM 
  auto-tags questions with topics from this list. ---
"""

from django.core.management.base import BaseCommand
from companies.tasks import scrape_and_ingest_questions
from companies.models import Topic, QuestionType


# Predefined topics for each question type
# --- NOTE: These are still created as Topic records even though we don't 
# scrape by topic anymore. They serve as the "taxonomy" that the LLM uses 
# for auto-tagging extracted questions. ---
SEED_TOPICS = {
    "DSA_CODING": [
        "arrays and strings", "linked lists", "binary search",
        "dynamic programming", "graphs and trees", "sliding window",
        "two pointers", "backtracking", "heap and priority queue",
    ],
    "DSA_THEORY": [
        "time complexity", "space complexity", "sorting algorithms",
        "hash tables", "recursion", "binary trees", "BFS DFS",
    ],
    "OS": [
        "process vs thread", "deadlock", "memory management",
        "virtual memory", "scheduling algorithms", "semaphores and mutex",
        "inter process communication", "page replacement algorithms",
    ],
    "DBMS": [
        "normalization", "SQL joins", "indexing", "transactions and ACID",
        "NoSQL vs SQL", "query optimization", "stored procedures",
        "database sharding",
    ],
    "NETWORKS": [
        "TCP vs UDP", "HTTP vs HTTPS", "DNS", "load balancing",
        "CDN", "OSI model", "REST vs GraphQL", "websockets",
    ],
    "SYSTEM_DESIGN": [
        "design URL shortener", "design Twitter", "design WhatsApp",
        "rate limiting", "caching strategies", "microservices vs monolith",
        "database design", "message queues",
    ],
}

# Companies to seed
# --- CHANGE (WHAT): Same list, but used differently. ---
# --- CHANGE (WHY): We now do ONE scrape per company that gets ALL question 
# types from their interview experiences, instead of one per topic. ---
SEED_COMPANIES = ["Google", "Amazon", "Sprinklr", "Tekion", "Cisco", "Oracle", "Meesho"]


class Command(BaseCommand):
    help = "Seed the question bank with topics and trigger experience scraping."

    def add_arguments(self, parser):
        parser.add_argument(
            "--company",
            type=str,
            help="Scrape experiences for this company only.",
        )
        parser.add_argument(
            "--all-companies",
            action="store_true",
            help="Scrape experiences for all seed companies (default).",
        )
        parser.add_argument(
            "--count",
            type=int,
            default=10,
            help="Target number of experience posts per company.",
        )
        parser.add_argument(
            "--no-scrape",
            action="store_true",
            help="Only create Topic records, don't trigger any scraping.",
        )
        # --- CHANGE (WHAT): Removed --type argument. ---
        # --- CHANGE (WHY): We no longer scrape by question type. The LLM 
        # auto-classifies questions from experience posts into all types. ---

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("=== Seeding question bank ===\n"))

        # ── Step 1: Create Topic records (taxonomy for LLM auto-tagging) ──────
        # --- CHANGE (WHAT): Still create all topics for all types. ---
        # --- CHANGE (WHY): Topic records serve as the classification taxonomy.
        # The LLM tags extracted questions with these topics. Even though we 
        # don't scrape by topic, we need the topic list for filtering later. ---
        self.stdout.write("Creating Topic records (taxonomy for question tagging)...")
        total_topics = 0
        
        for qtype, topics in SEED_TOPICS.items():
            for topic_name in topics:
                topic, created = Topic.objects.get_or_create(
                    name=topic_name,
                    defaults={"question_type": qtype},
                )
                if created:
                    self.stdout.write(f"  ✓ Created topic: {topic_name} ({qtype})")
                total_topics += 1

        self.stdout.write(f"  Total topics available: {total_topics}\n")

        if options["no_scrape"]:
            self.stdout.write(
                self.style.SUCCESS(
                    "Done! Topic taxonomy created. No scraping triggered.\n"
                    "Run without --no-scrape to populate questions."
                )
            )
            return

        # ── Step 2: Trigger experience scraping (one task per company) ─────────
        # --- CHANGE (WHAT): Single task per company, no nested loops. ---
        # --- CHANGE (WHY): Each task scrapes interview experience posts.
        # The LLM extracts ALL question types from each post. One company's 
        # interview experience typically contains DSA, System Design, and 
        # theory questions all in one post — we get everything at once. ---
        
        companies = [options["company"]] if options["company"] else SEED_COMPANIES
        
        self.stdout.write(f"Queuing scraping tasks for {len(companies)} companies...\n")
        
        for i, company in enumerate(companies, 1):
            # --- CHANGE (WHAT): Pass empty question_type. ---
            # --- CHANGE (WHY): LLM auto-classifies. We don't restrict to one type.
            # The topic_hint is generic to help Serper find relevant posts. ---
            task = scrape_and_ingest_questions.delay(
                question_type="",              # Let LLM classify all types
                company_name=company,
                topic_name="",                # No specific topic — get all experiences
                target_count=options["count"],
            )
            self.stdout.write(
                f"  [{i}/{len(companies)}] {company} — task_id={task.id}"
            )

        # --- CHANGE (WHAT): Updated summary message. ---
        # --- CHANGE (WHY): Reflects new approach: 1 task per company that 
        # extracts all question types from experience posts. ---
        self.stdout.write(
            self.style.SUCCESS(
                f"\n✓ Queued {len(companies)} scraping tasks.\n"
                f"  Each task will:\n"
                f"    1. Search for {options['count']} interview experience posts\n"
                f"    2. Extract ALL questions with auto-classified types\n"
                f"    3. Tag questions with relevant topics\n"
                f"    4. Generate embeddings for duplicate detection\n"
                f"    5. Generate reference answers for unique questions\n\n"
                f"  Monitor: celery -A interview_prep worker -l info"
            )
        )