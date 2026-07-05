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
  questions with their auto-classified categories.

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
  
"""

from django.core.management.base import BaseCommand
from companies.tasks import scrape_and_ingest_questions

# Companies to seed
# --- CHANGE (WHAT): Same list, but used differently. ---
# --- CHANGE (WHY): We now do ONE scrape per company that gets ALL question 
# types from their interview experiences, instead of one per topic. ---
SEED_COMPANIES = ["Google", "Amazon", "Sprinklr", "Tekion", "Cisco", "Oracle", "Meesho"]


class Command(BaseCommand):
    help = "Seed the question bank by triggering focused experience scraping."

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
            help="Validate companies but don't trigger any scraping.",
        )
        # --- CHANGE (WHAT): Removed --type argument. ---
        # --- CHANGE (WHY): We no longer scrape by question type. The LLM 
        # auto-classifies questions from experience posts into all types. ---

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("=== Seeding question bank ===\n"))

        if options["no_scrape"]:
            self.stdout.write(
                self.style.SUCCESS(
                    "No scraping triggered.\nRun without --no-scrape to populate questions."
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
            task = scrape_and_ingest_questions.delay(
                question_type="",              # Let LLM classify all types
                company_name=company,
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
                f"    3. Generate embeddings for duplicate detection\n"
                f"    4. Generate reference answers for unique questions\n\n"
                f"  Monitor: celery -A interview_prep worker -l info"
            )
        )
