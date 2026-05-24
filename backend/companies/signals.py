from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import PlacementExperience
from .tasks import update_company_ai_analysis

@receiver(post_save, sender=PlacementExperience)
def trigger_ai_enrichment(sender, instance, created, **kwargs):
    """
    If a new interview experience is added, trigger the background 
    Celery worker to recalculate the AI insights for that company.
    """
    if created:  # Only run if this is a BRAND NEW experience
        # Send the task to Redis immediately. Do NOT wait for the result.
        update_company_ai_analysis.delay(instance.company.id)