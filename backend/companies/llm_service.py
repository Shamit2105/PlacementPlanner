"""
LLM Service — Google Gemini (Free Tier) + Local HuggingFace Embeddings
=====================================================================
Wraps the google-generativeai SDK for generation tasks and 
HuggingFace local models for embeddings:

  1. format_questions()      — clean scraped text → MULTIPLE interview-style questions with topic classification
  2. generate_answer()       — write a reference answer for a question
  3. evaluate_answer()       — judge a candidate's answer vs the reference
  4. generate_unique_question() — synthesize a new question when scraping fails
  5. get_embedding()         — 768-dim vector for semantic search (local HF model)

CHANGES:
  - format_question() → format_questions(): Now extracts ALL possible questions instead of just one
  - Added topic classification: LLM now determines question_type instead of receiving it as parameter
  - Removed question_type parameter from format_questions()
  - Increased max_output_tokens to handle multiple questions
  - Returns list of dicts with question text AND classified topic tags

FREE TIER RATE LIMITS (as of 2024):
  • gemini-1.5-flash : 15 RPM, 1,000,000 TPD
  → We add time.sleep() after every call to stay under limits.
  → GEMINI_SLEEP_SECONDS (default 4s) between generation calls

LOCAL EMBEDDINGS:
  Uses a locally installed HuggingFace sentence-transformer model
  No rate limits, no API costs for embeddings

HOW TO USE:
  from questions.llm_service import LLMService
  svc = LLMService()
  questions = svc.format_questions("What is a binary tree? How to traverse it?", company="Google")
  # Returns: [{"question": "...", "question_type": "DSA_THEORY", "topic_tags": ["binary-tree", "traversal"]}, ...]
"""

import time, os
import logging
import re
import json
from typing import Optional, List, Dict
from django.conf import settings

from sentence_transformers import SentenceTransformer
from langchain_groq import ChatGroq
from langchain_core.output_parsers import JsonOutputParser, StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate
from langchain_core.messages import SystemMessage, HumanMessage

logger = logging.getLogger(__name__)
os.environ["TOKENIZERS_PARALLELISM"] = "false"


class LLMService:
    GENERATION_MODEL = 'meta-llama/llama-4-scout-17b-16e-instruct'

    EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

    _cached_embedding_model = None

    def __init__(self):
        if not settings.GROQ_API_KEY:
            raise ValueError("GroqAPI Key Not Set")


        self.llm = ChatGroq(api_key=settings.GROQ_API_KEY,model=self.GENERATION_MODEL,
                            temperature=0.2,max_tokens=1024)

        self.llm_long = ChatGroq(api_key=settings.GROQ_API_KEY,model=self.GENERATION_MODEL,
                                 temperature=0.2,max_tokens=4096)
        
        self.json_parser = JsonOutputParser()

        self.str_parser = StrOutputParser()


        if LLMService._cached_embedding_model is None:
            logger.info("Loading local embedding model into worker memory...")
            LLMService._cached_embedding_model = SentenceTransformer(self.EMBEDDING_MODEL)
        
        self.embedding_model = LLMService._cached_embedding_model
        self.sleep_seconds = 4  # Reduced for Groq
        self.embed_sleep_seconds = 0

    def _coding_note_for_type(self, question_type: str) -> str:
        """
        Return the answer-structure instruction for a given question type.
        Extracted into a helper so it can be reused by both generate_answer()
        and generate_answer_with_rag() without duplication.
        """
        if question_type == "DSA_CODING":
            return (
                "Include:  (1) brute force approach in brief, "
                "(2) optimized c++ code with time/space complexity, "
                ""
            )
        elif question_type == "SYSTEM_DESIGN":
            return (
                "Structure: (1) clarify requirements, (2) high-level design, "
                "(3) component deep-dive, (4) scalability considerations, "
                "(5) trade-offs."
            )
        else:
            return (
                "Structure: (1) direct answer, (2) brief explanation, "
                "(3) real-world example or analogy,"
            )

        

    def _generate(self, prompt: str, max_output_tokens: int = 1024, force_json: bool = False) -> str:
        """Call Groq via LangChain with optional JSON constraints."""
        try:
            # Choose LLM instance based on token needs
            llm = self.llm_long if max_output_tokens > 1024 else self.llm
            
            if force_json:
                # Use system message for JSON enforcement
                messages = [
                    SystemMessage(content="You are a helpful assistant that always responds in valid JSON format. Never wrap JSON in markdown code blocks."),
                    HumanMessage(content=prompt)
                ]
                response = llm.invoke(messages)
            else:
                response = llm.invoke(prompt)
            
            raw_text = response.content.strip()
            
            logger.debug("Groq LangChain call succeeded. Sleeping %.1fs...", self.sleep_seconds)
            time.sleep(self.sleep_seconds)
            return raw_text
        
        except Exception as exc:
            logger.error("Groq generation failed: %s", exc)
            time.sleep(self.sleep_seconds * 2)
            raise

    def format_questions(self, raw_text: str, company: str = "", topic_hint: str = "") -> List[Dict]:
        company_ctx = f" from a {company} interview" if company else ""
        topic_ctx = f" The content is about '{topic_hint}'." if topic_hint else ""

        prompt = f"""Extract all technical interview questions{company_ctx} from the text below and convert each into a nice
         detailed verbose interview question.{topic_ctx}
        Return a JSON array where each object contains exactly these fields:
        - "question": string (the interview question formatted cleanly in detail what the problem is 
        and if it is a coding question, a sample testcase with expected answer of that testcase) 
        - "question_type": exactly one of: DSA_CODING, DSA_THEORY, OS, DBMS, NETWORKS, SYSTEM_DESIGN
        - "topic_tags": array of 2-4 lowercase hyphenated strings

        Text to parse:
        ---
        {raw_text[:4000]}
        ---"""

        try:
            format_chain=(ChatPromptTemplate.from_messages(
                [SystemMessage(
                    content="Extract and format interview questions. Respond ONLY with a JSON array."
                ),
                    HumanMessage(content=prompt)
                ])
                | self.llm_long
                | self.json_parser
            )

            questions= format_chain.invoke({})
        
        except Exception as exc:
            logger.error("format_questions execution failed: %s", exc)
            return []
        
        valid_types = {"DSA_CODING", "DSA_THEORY", "OS", "DBMS", "NETWORKS", "SYSTEM_DESIGN"}
        results = []
        
        if isinstance(questions, list):
            for q in questions:
                if not isinstance(q, dict) or not q.get("question", "").strip():
                    continue
                if q.get("question_type") not in valid_types:
                    q["question_type"] = "DSA_THEORY"
                q["topic_tags"] = [t.lower().strip() for t in q.get("topic_tags", []) if t]
                results.append(q)

        logger.info("Extracted %d questions from raw text", len(results))
        return results

        
    def generate_answer(self, interview_question: str, question_type: str) -> str:
        """
        Write a comprehensive reference answer in interview style.

        WHY: We store reference answers so users can compare their response
        with an ideal answer after the mock interview. This is the core
        learning mechanism.

        The answer is written as "what you should say in an interview" —
        not a textbook essay. It should be structured, clear, and include
        examples/code where helpful.

        Args:
            interview_question: The clean question text.
            question_type: Drives answer style (code for DSA_CODING, prose for theory).

        Returns:
            A structured reference answer string.
        """
        
        coding_note = self._coding_note_for_type(question_type)
        
        # LangChain prompt template
        answer_prompt = ChatPromptTemplate.from_messages([
            SystemMessage(content="You are a senior software engineer answering in a technical interview. Answer " \
            "clear, structured, confident."),
            HumanMessage(content=f"""{coding_note}

    Question: {interview_question}

    Answer (interview style):""")
        ])
        
        # Create chain
        answer_chain = answer_prompt | self.llm_long | self.str_parser
        
        return answer_chain.invoke({
            "coding_note": coding_note,
            "interview_question": interview_question
        })
    
    def generate_answer_with_rag(self,interview_question: str,question_type: str,company_slug: str = "",) -> str:
        """Write a reference answer augmented with retrieved similar Q+A pairs."""
        coding_note = self._coding_note_for_type(question_type)
        
        # Retrieve similar Q+A pairs
        examples = self.rag.retrieve_similar_qa_pairs(
            question_text=interview_question,
            question_type=question_type,
            company_slug=company_slug if company_slug else None,
        )
        
        few_shot_block = self.rag.build_few_shot_block(examples)
        
        if few_shot_block:
            logger.info("RAG: injecting %d examples for answer generation", len(examples))
        else:
            logger.info("RAG: no examples found — falling back to cold generation")
        
        # LangChain RAG prompt
        rag_prompt = ChatPromptTemplate.from_messages([
            SystemMessage(content="You are a senior software engineer answering in a technical interview."),
            HumanMessage(content="""{few_shot_examples}

    {coding_note}

    Question: {interview_question}

    Answer (interview style, following the structure of examples above if provided):""")
        ])
        
        rag_chain = rag_prompt | self.llm_long | self.str_parser
        
        return rag_chain.invoke({
            "few_shot_examples": few_shot_block if few_shot_block else "",
            "coding_note": coding_note,
            "interview_question": interview_question
        })

    def evaluate_answer(self,interview_question: str,reference_answer: str,candidate_answer: str,question_type: str,
                        ) -> dict:
        
        """Judge a candidate's answer against the reference answer."""
        
        eval_prompt = ChatPromptTemplate.from_messages([
            SystemMessage(content="You are a strict but fair technical interviewer evaluating a candidate's answer. Respond ONLY in valid JSON."),
            HumanMessage(content="""Question: {interview_question}

    Reference Answer (ideal):
    {reference_answer}

    Candidate's Answer:
    {candidate_answer}

    Evaluate and respond in this exact JSON format:
    {{
    "score": <integer 0-10>,
    "verdict": "<Strong|Acceptable|Needs Work>",
    "feedback": "<2-3 sentence overall assessment>",
    "strengths": ["<point 1>", "<point 2>"],
    "improvements": ["<gap 1>", "<gap 2>"],
    "missed_concepts": ["<concept they didn't mention>"]
    }}""")
        ])
        
        eval_chain = eval_prompt | self.llm | self.json_parser
        
        try:
            result = eval_chain.invoke({
                "interview_question": interview_question,
                "reference_answer": reference_answer,
                "candidate_answer": candidate_answer
            })
            return result
        except Exception as e:
            logger.warning("JSON parse failed, falling back to manual: %s", e)
            # Fallback to old method
            raw = self._generate(str(eval_prompt), force_json=True)
            return self._parse_evaluation_json(raw)

    def generate_unique_question(self,question_type: str,company: str = "",topic: str = "",
                                 existing_questions: list[str] | None = None,) -> dict:
        """Synthesize a brand-new question when scraping doesn't yield enough."""
        
        avoid_block = ""
        if existing_questions:
            samples = "\n".join(f"- {q[:120]}" for q in existing_questions[:10])
            avoid_block = f"\nDo NOT generate questions similar to these existing ones:\n{samples}"
        
        company_ctx = f" (commonly asked at {company})" if company else ""
        topic_ctx = f" on the topic of '{topic}'" if topic else ""
        
        type_label = {
            "DSA_CODING": "algorithmic coding problem",
            "DSA_THEORY": "data structures / algorithms concept question",
            "OS": "operating systems interview question",
            "DBMS": "database management interview question",
            "NETWORKS": "computer networks interview question",
            "SYSTEM_DESIGN": "system design interview question",
        }.get(question_type, "technical interview question")
        
        gen_prompt = ChatPromptTemplate.from_messages([
            SystemMessage(content="Generate original technical interview questions. Respond ONLY in JSON format."),
            HumanMessage(content="""Generate one original {type_label}{company_ctx}{topic_ctx}.
    {avoid_block}

    Respond in this JSON format:
    {{
    "question": "<the interview question, 1-4 sentences>",
    "answer": "<comprehensive reference answer in interview style>",
    "difficulty": "<Easy|Medium|Hard>"
    }}""")
        ])
        
        gen_chain = gen_prompt | self.llm_long | self.json_parser
        
        try:
            return gen_chain.invoke({
                "type_label": type_label,
                "company_ctx": company_ctx,
                "topic_ctx": topic_ctx,
                "avoid_block": avoid_block
            })
        except Exception:
            logger.warning("Could not parse generated question JSON")
            return {"question": "", "answer": "", "difficulty": "Medium"}

    def get_embedding(self, text: str) -> Optional[list[float]]:
        """
        Get embedding vector using local HuggingFace model for semantic search via pgvector.

        WHY: Storing embeddings allows us to find semantically similar questions
        (deduplication) and retrieve the most relevant questions for a given
        company/topic combination without exact keyword matching.

        Uses the locally installed sentence-transformer model — no API calls,
        no rate limits, instant responses.

        Returns:
            List of floats (embedding dimension depends on the model),
            or None if the call failed.
        """
        try:
            # Truncate text if needed (most sentence-transformers handle this well)
            truncated_text = text[:2048] if len(text) > 2048 else text
            
            # Generate embedding using local model
            embedding = self.embedding_model.encode(truncated_text)
            
            logger.debug("Local embedding computed (%d dims)", len(embedding))
            # No rate limiting needed for local model
            if self.embed_sleep_seconds > 0:
                time.sleep(self.embed_sleep_seconds)
            
            return embedding.tolist()  # Convert numpy array to list
        except Exception as exc:
            logger.error("Local embedding failed: %s", exc)
            if self.embed_sleep_seconds > 0:
                time.sleep(self.embed_sleep_seconds)
            return None

    def get_query_embedding(self, text: str) -> Optional[list[float]]:
        """
        Embedding for a search query using local HuggingFace model.
        For sentence-transformers, we can use the same encoding for both
        documents and queries (though some models have asymmetric methods).
        """
        try:
            # Truncate text if needed
            truncated_text = text[:2048] if len(text) > 2048 else text
            
            # Generate embedding using local model
            embedding = self.embedding_model.encode(truncated_text)
            
            logger.debug("Local query embedding computed (%d dims)", len(embedding))
            if self.embed_sleep_seconds > 0:
                time.sleep(self.embed_sleep_seconds)
            
            return embedding.tolist()  # Convert numpy array to list
        except Exception as exc:
            logger.error("Local query embedding failed: %s", exc)
            if self.embed_sleep_seconds > 0:
                time.sleep(self.embed_sleep_seconds)
            return None