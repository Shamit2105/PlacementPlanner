import json
import os
from django.core.management.base import BaseCommand
from companies.models import Company, PlacementExperience
from pathlib import Path
from django.conf import settings

class Command(BaseCommand):
    help = 'Seeds the PostgreSQL database with scraped data from django_seed_data.json'
    
    def handle(self, *args, **kwargs):
        file_path = settings.BASE_DIR.parent.parent / 'scraper' / 'django_seed_data.json'
        
        if not os.path.exists(file_path):
            self.stdout.write(self.style.ERROR(f"[-] File not found at {file_path}. Run your scraper first!"))
            return

        with open(file_path, 'r', encoding='utf-8') as file:
            data = json.load(file)

        self.stdout.write(self.style.NOTICE(f"[*] Found {len(data)} records in JSON. Starting ingestion..."))

        new_records = 0
        duplicate_records = 0

        for entry in data:
            # 1. Get or Create the Company
            company, created = Company.objects.get_or_create(
                name=entry['company']
            )
            if created:
                 self.stdout.write(self.style.SUCCESS(f"  [+] Created new Company profile: {company.name}"))

            # 2. Map the JSON round_type to the Django Model CHOICES
            # The scraper outputs "OA" or "Interview", but our model uses "OA" and "INTERVIEW"
            raw_round_type = entry.get('round_type', 'Interview').upper()
            db_round_type = 'OA' if raw_round_type == 'OA' else 'INTERVIEW'

            experience, exp_created = PlacementExperience.objects.get_or_create(
                source_url=entry['source_url'], # This is the unique identifier
                defaults={
                    'company': company,
                    'round_type': db_round_type,
                    'target_role': entry.get('target_role', 'Software Engineer'),
                    'batch_year': entry.get('batch_year'),
                    'source_platform': entry.get('source_platform', 'Unknown'),
                    'raw_text': entry.get('raw_text', ''),
                    # is_vectorized is defaulted to False automatically!
                }
            )

            if exp_created:
                new_records += 1
                self.stdout.write(self.style.SUCCESS(f"  [✓] Added new {db_round_type} for {company.name}"))
            else:
                duplicate_records += 1
                self.stdout.write(self.style.WARNING(f"  [~] Skipped duplicate URL for {company.name}"))

        self.stdout.write(self.style.SUCCESS("Database Seeding Completed!"))
        self.stdout.write(self.style.SUCCESS(f"New Records Added: {new_records}"))
        self.stdout.write(self.style.WARNING(f"Duplicates Skipped: {duplicate_records}"))