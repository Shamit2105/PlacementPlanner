import os
from django.core.management.base import BaseCommand
from django.conf import settings
from companies.models import PlacementExperience
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter

class Command(BaseCommand):
    help = 'Chunks experiences and saves them to ChromaDB using local HuggingFace embeddings.'

    def handle(self, *args, **kwargs):
        # 1. FIND READY RECORDS
        unprocessed_records = PlacementExperience.objects.filter(
            is_extracted=True, 
            is_vectorized=False
        )

        if not unprocessed_records.exists():
            self.stdout.write(self.style.SUCCESS("[✓] All extracted records are already in ChromaDB!"))
            return

        self.stdout.write(self.style.NOTICE(f"[*] Found {unprocessed_records.count()} records. Booting local AI..."))

        # 2. INITIALIZE LOCAL EMBEDDINGS (No API Keys needed!)
        # all-MiniLM-L6-v2 is the industry standard for fast, accurate local embeddings
        self.stdout.write("  [~] Downloading/Loading local embedding model (this takes a few seconds the first time)...")
        embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
        
        persist_directory = os.path.join(settings.BASE_DIR, 'chroma_db')
        vector_store = Chroma(
            collection_name="placement_interviews",
            embedding_function=embeddings,
            persist_directory=persist_directory
        )

        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
        success_count = 0

        # 3. PROCESS THE DATABASE (Lightning Fast, No Sleeps!)
        for exp in unprocessed_records:
            self.stdout.write(f"  [~] Vectorizing {exp.company.name} ({exp.get_round_type_display()})...")
            
            try:
                raw_text = exp.raw_text or ""
                raw_chunks = text_splitter.split_text(raw_text)
                chunks = [c for c in raw_chunks if c.strip()]
                
                if not chunks:
                    self.stdout.write(self.style.WARNING("      [-] Skipped: No valid text found."))
                    exp.is_vectorized = True 
                    exp.save()
                    continue
                
                dsa_string = ", ".join(exp.extracted_dsa_questions) if exp.extracted_dsa_questions else "None"
                core_string = ", ".join(exp.extracted_core_topics) if exp.extracted_core_topics else "None"

                # We can do this in one massive batch now because there are no API safety filters!
                metadatas = [{
                    "experience_id": exp.id,
                    "company": exp.company.name,
                    "round_type": exp.get_round_type_display(),
                    "dsa_topics_present": dsa_string,
                    "core_topics_present": core_string
                } for _ in chunks]

                # Send straight to local ChromaDB
                vector_store.add_texts(texts=chunks, metadatas=metadatas)
                
                exp.is_vectorized = True
                exp.save()
                success_count += 1
                self.stdout.write(self.style.SUCCESS(f"      -> Successfully added {len(chunks)} chunks."))

            except Exception as e:
                 self.stdout.write(self.style.ERROR(f"      [-] Fatal error: {e}"))
                 
        self.stdout.write(self.style.SUCCESS(f"\n[✓] Successfully vectorized {success_count} records locally!"))