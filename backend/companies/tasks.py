import logging
from celery import shared_task
from .models import Company, PlacementExperience
from .ai_company_engine import enrich_company_questions

logger = logging.getLogger('companies')

@shared_task
def update_company_ai_analysis(company_id):
    """
    Background task: Takes a single company ID, grabs all its questions,
    calls Gemini, and updates the trend analysis JSON.
    """
    try:
        company = Company.objects.get(id=company_id)
        
        # Grab all questions for this specific company
        experiences = PlacementExperience.objects.filter(company=company)
        all_questions = []
        for exp in experiences:
            if isinstance(exp.extracted_dsa_questions, list):
                all_questions.extend(exp.extracted_dsa_questions)
            
            if isinstance(exp.extracted_core_topics, list):
                all_questions.extend(exp.extracted_core_topics)
                
        unique_questions = list(set(all_questions))
        
        if not unique_questions:
            return f"No questions found for {company.name}"

        # Hit the AI Engine (this takes ~3-5 seconds, which is why it's in the background!)
        ai_data = enrich_company_questions(company.name, unique_questions)
        
        if ai_data:
            company.ai_trend_analysis = ai_data
            company.save()
            return f"Successfully enriched {company.name}"
        
        return f"AI Engine failed for {company.name}"

    except Company.DoesNotExist:
        logger.error(f"Celery Task Error: Company {company_id} not found.")
        return "Company not found"
    except Exception as e:
        logger.error(f"Celery Task Exception: {e}")
        return "Task failed"