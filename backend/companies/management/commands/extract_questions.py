import os
import json
import time
from dotenv import load_dotenv
from django.core.management.base import BaseCommand
from companies.models import PlacementExperience
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

class InterviewExtraction(BaseModel):
    dsa_questions: list[str] = Field(description="List of specific coding/DSA questions or puzzle statements asked.")
    core_topics: list[str] = Field(description="List of core CS topics mentioned (e.g., OS, DBMS, Networks, System Design).")

class Command(BaseCommand):
    help = 'Runs Gemini over raw_text to populate the extracted JSON fields.'

    def handle(self, *args, **kwargs):
       
        if not GOOGLE_API_KEY:
            self.stdout.write(self.style.ERROR("[-] ERROR: GOOGLE_API_KEY is missing from your .env file!"))
            return
        
        unprocessed_records = PlacementExperience.objects.filter(
            extracted_dsa_questions=[], 
            extracted_core_topics=[],
            is_extracted=False
        )


        if not unprocessed_records.exists():
            self.stdout.write(self.style.SUCCESS("[✓] All records have already been extracted!"))
            return

        self.stdout.write(self.style.NOTICE(f"[*] Found {unprocessed_records.count()} records to process. Booting Gemini..."))
        self.stdout.write(self.style.WARNING(f"[*] DEBUG: API Key being used starts with: {GOOGLE_API_KEY[:5]}"))
        llm = ChatGoogleGenerativeAI(
            model="gemma-4-31b-it", 
            temperature=0.0,
            api_key=GOOGLE_API_KEY  
        )
        
        structured_llm = llm.with_structured_output(InterviewExtraction)

        prompt = ChatPromptTemplate.from_messages([
            ("system", "You are an expert data extractor. Read the following interview experience and "
            "extract the requested data. If no DSA questions or core topics are found, return an empty list."
            " Do not invent information."),
            ("user", "RAW TEXT:\n\n{raw_text}")
        ])

        extraction_chain = prompt | structured_llm

        success_count = 0
        
        for exp in unprocessed_records:
            self.stdout.write(f"  [~] Extracting data for {exp.company.name} ({exp.get_round_type_display()})...")
            max_retries=3
            for attempt in range(max_retries):
                try:
                    result = extraction_chain.invoke({"raw_text": exp.raw_text})
                    
                    exp.extracted_dsa_questions = result.dsa_questions
                    exp.extracted_core_topics = result.core_topics
                    exp.is_extracted = True
                    exp.raw_text = ""
                    exp.save()
                    
                    success_count += 1
                    self.stdout.write(self.style.SUCCESS(f"      -> Found {len(result.dsa_questions)} DSA, {len(result.core_topics)} Core"))
                    
                    time.sleep(5)
                    break
                except Exception as e:
                    error_msg = str(e)

                    if "429" in error_msg or "Resource_Exhausted" in error_msg:
                        self.stdout.write(self.style.WARNING(f"     [!] Rate Limit Hit, Sleeping for 60 seconds!"))
                        self.stdout.write(self.style.WARNING(f"{error_msg}"))
                        time.sleep(60)
                    else:
                        self.stdout.write(self.style.ERROR(f"      -> Failed to extract: {e}"))
                        break

        self.stdout.write(self.style.SUCCESS(f"\n[✓] Successfully extracted data for {success_count} records!"))