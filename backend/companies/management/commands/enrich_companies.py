import time
from django.core.management.base import BaseCommand
from companies.models import Company
from companies.tasks import update_company_ai_analysis

class Command(BaseCommand):
    help = 'Batch processes AI trend analysis for all missing companies.'

    def handle(self, *args, **kwargs):
        companies_to_enrich = Company.objects.filter(ai_trend_analysis__isnull=True)
        total = companies_to_enrich.count()

        if total == 0:
            self.stdout.write(self.style.SUCCESS('All companies are already enriched!'))
            return

        for index, company in enumerate(companies_to_enrich, start=1):
            self.stdout.write(f"[{index}/{total}] Queueing analysis for {company.name}...")
            
            # Instead of writing the AI logic here, just call the Celery function synchronously 
            # (Without .delay() so it runs right here in the terminal, respecting the time.sleep)
            result = update_company_ai_analysis(company.id)
            
            self.stdout.write(self.style.SUCCESS(f"  -> {result}"))

            # Protect the Gemini 15 RPM Free Tier limit
            time.sleep(4)
            
        self.stdout.write(self.style.SUCCESS('Pipeline Complete!'))