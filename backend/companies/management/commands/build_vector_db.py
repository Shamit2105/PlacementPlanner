import os
from django.core.management.base import BaseCommand
from django.conf import settings
from companies.models import PlacementExperience
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_postgres import PGVector
from langchain_text_splitters import RecursiveCharacterTextSplitter

class Command(BaseCommand):
    help = 'Chunks experiences and saves them to PGVector using local HuggingFace embeddings.'

    def handle(self, *args, **kwargs):
        # 1. FIND READY RECORDS
        unprocessed_records = PlacementExperience.objects.filter(
            is_extracted=True, 
            is_vectorized=False
        )

        if not unprocessed_records.exists():
            self.stdout.write(self.style.SUCCESS("[✓] All extracted records are already in PlacementPrepDB!"))
            return

        self.stdout.write(self.style.NOTICE(f"[*] Found {unprocessed_records.count()} records. Booting local AI..."))

        # 2. INITIALIZE LOCAL EMBEDDINGS
        self.stdout.write("  [~] Downloading/Loading local embedding model...")
        embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
        
        # 3. CONSTRUCT PGVECTOR CONNECTION STRING
        # Langchain needs a specific sqlalchemy-compatible string: postgresql+psycopg://
        db_config = settings.DATABASES['default']
        connection_string = f"postgresql+psycopg://{db_config['USER']}:{db_config['PASSWORD']}@{db_config['HOST']}:{db_config['PORT']}/{db_config['NAME']}"

        # 4. INITIALIZE PGVECTOR
        vector_store = PGVector(
            embeddings=embeddings,
            collection_name="placement_interviews",
            connection=connection_string,
            use_jsonb=True, # Stores your metadata efficiently
        )

        # 5. INITIALIZE TEXT SPLITTER
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            length_function=len,
            is_separator_regex=False,
        )

        success_count = 0

        self.stdout.write(self.style.NOTICE("\n[*] Starting Vectorization Process..."))
        
        # 6. PROCESS AND STORE CHUNKS
        for exp in unprocessed_records:
            try:
                self.stdout.write(f"  [+] Processing: {exp.company.name} ({exp.get_round_type_display()})")
                
                clean_text_lines = []

                if exp.extracted_dsa_questions:
                    clean_text_lines.extend(exp.extracted_dsa_questions)
                    
                if exp.extracted_core_topics:
                    clean_text_lines.extend(exp.extracted_core_topics)

                if not clean_text_lines:
                    self.stdout.write(self.style.WARNING("      [-] Skipped: No questions were extracted by Gemini."))
                    exp.is_vectorized = True 
                    exp.save()
                    continue
                
                combined_clean_text = "\n\n".join(clean_text_lines)
                
                # Now split the CLEAN text, not the raw text
                chunks = text_splitter.split_text(combined_clean_text)

                if not chunks:
                    self.stdout.write(self.style.WARNING("      [-] Skipped: No valid text found."))
                    exp.is_vectorized = True 
                    exp.save()
                    continue
                
                dsa_string = ", ".join(exp.extracted_dsa_questions) if exp.extracted_dsa_questions else "None"
                core_string = ", ".join(exp.extracted_core_topics) if exp.extracted_core_topics else "None"

                # Generate metadata for hybrid filtering later
                metadatas = [{
                    "experience_id": exp.id,
                    "company": exp.company.name,
                    "round_type": exp.get_round_type_display(),
                    "dsa_topics_present": dsa_string,
                    "core_topics_present": core_string
                } for _ in chunks]

                # Send straight to PostgreSQL pgvector tables!
                vector_store.add_texts(texts=chunks, metadatas=metadatas)
                
                exp.is_vectorized = True
                exp.save()
                success_count += 1
                self.stdout.write(self.style.SUCCESS(f"      -> Successfully added {len(chunks)} chunks to PGVector."))

            except Exception as e:
                 self.stdout.write(self.style.ERROR(f"      [-] Fatal error: {e}"))
                 
        self.stdout.write(self.style.SUCCESS(f"\n[✓] Successfully vectorized {success_count} records to PlacementPrepDB!"))