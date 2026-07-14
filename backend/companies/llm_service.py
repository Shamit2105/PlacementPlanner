import json
import logging
import re
from typing import Optional

from django.conf import settings
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.output_parsers import JsonOutputParser, StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq
from sentence_transformers import SentenceTransformer

from .prompts import (
    CODING_ANSWER_PROMPT,
    CODING_EVALUATION_PROMPT,
    QUESTION_EXTRACTION_PROMPT,
    RUBRIC_PROMPT,
    THEORY_ANSWER_PROMPT,
    THEORY_EVALUATION_PROMPT,
)
from .models import QuestionType

logger = logging.getLogger(__name__)

ALLOWED_QUESTION_TYPES = {choice.value for choice in QuestionType}


class LLMService:
    MODEL = "openai/gpt-oss-20b"

    EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

    _embedding_model = None

    def __init__(self):

        self.generator = ChatGroq(
            api_key=settings.GROQ_API_KEY,
            model=self.MODEL,
            temperature=0.2,
            max_tokens=4096,
        )

        self.evaluator = ChatGroq(
            api_key=settings.GROQ_API_KEY,
            model=self.MODEL,
            temperature=0,
            max_tokens=2048,
        )

        self.json = JsonOutputParser()

        self.text = StrOutputParser()

        if LLMService._embedding_model is None:
            logger.info("Loading embedding model...")

            LLMService._embedding_model = SentenceTransformer(self.EMBEDDING_MODEL)

        self.embedding_model = LLMService._embedding_model

    def _json(
        self,
        system_prompt,
        user_prompt,
        eval=False,
    ):

        chain = (
            ChatPromptTemplate.from_messages(
                [
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=user_prompt),
                ]
            )
            | (self.evaluator if eval else self.generator)
            | self.json
        )

        return chain.invoke({})

    def _text(
        self,
        system_prompt,
        user_prompt,
    ):

        chain = (
            ChatPromptTemplate.from_messages(
                [
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=user_prompt),
                ]
            )
            | self.generator
            | self.text
        )

        return chain.invoke({})

    def extract_questions(
        self,
        text,
    ):

        prompt = f"""{text}"""

        try:
            return self._json(
                QUESTION_EXTRACTION_PROMPT,
                prompt,
            )

        except Exception as e:
            logger.exception(e)

            return []

    def format_questions(
        self,
        raw_text: str,
        company: str = "",
    ) -> list[dict]:
        context = []
        if company:
            context.append(f"Company: {company}")

        prompt = "\n\n".join(context + [raw_text])
        questions = self.extract_questions(prompt)
        return self._normalize_questions(questions)

    def _normalize_questions(self, questions) -> list[dict]:
        if not isinstance(questions, list):
            return []

        cleaned = []
        seen = set()
        for item in questions:
            if not isinstance(item, dict):
                continue

            question = str(item.get("question", "")).strip()
            question_type = str(item.get("question_type", "")).strip().upper()
            if not question or question_type not in ALLOWED_QUESTION_TYPES:
                continue

            key = re.sub(r"\s+", " ", question.lower())
            if key in seen:
                continue
            seen.add(key)

            cleaned.append(
                {
                    "question": question,
                    "question_type": question_type,
                }
            )

        return cleaned

    def generate_answer(
        self,
        question,
        question_type,
    ):

        prompt = f"""Question: {question}"""

        if question_type == "DSA_CODING":
            return self._text(
                CODING_ANSWER_PROMPT,
                prompt,
            )

        return self._text(
            THEORY_ANSWER_PROMPT,
            prompt,
        )

    def generate_rubric(
        self,
        question,
        question_type,
    ):

        prompt = f"""
    Question Type

    {question_type}

    Question

    {question}
    """

        try:
            return self._json(
                RUBRIC_PROMPT,
                prompt,
            )

        except Exception as e:
            logger.exception(e)

            return {
                "algorithm": {
                    "value": "",
                    "weight": 40,
                },
                "time_complexity": {
                    "value": "",
                    "weight": 15,
                },
                "space_complexity": {
                    "value": "",
                    "weight": 10,
                },
                "required_concepts": [],
                "optional_concepts": [],
                "edge_cases": [],
                "common_mistakes": [],
                "difficulty": "Medium",
            }

    def generate_evaluation_rubric(
        self,
        question,
        question_type,
    ):
        return self.generate_rubric(question, question_type)

    def generate_unique_question(
        self,
        question_type: str,
        company: str = "",
        existing_questions: Optional[list[str]] = None,
    ) -> dict:
        existing_questions = existing_questions or []
        prompt = f"""
Question type: {question_type}
Company: {company or "Any"}

Avoid questions similar to:
{json.dumps(existing_questions[:50], indent=2)}

Return ONLY JSON:
{{
    "question": "",
    "answer": "",
    "difficulty": "Medium"
}}
"""
        try:
            result = self._json(
                "Generate one original technical interview question and a concise reference answer.",
                prompt,
            )
            if not isinstance(result, dict):
                return {}
            return result
        except Exception as e:
            logger.exception(e)
            return {}

    def _is_code_answer(
        self,
        answer,
    ):

        patterns = [
            "#include",
            "using namespace",
            "class Solution",
            "int main",
            "vector<",
            "unordered_map",
            "unordered_set",
            "priority_queue",
            "std::",
        ]

        answer = answer.lower()

        return any(p.lower() in answer for p in patterns)

    def _hallucinated(
        self,
        question,
        rubric,
        candidate,
        feedback,
    ):

        corpus = (question + json.dumps(rubric) + candidate).lower()

        suspicious = [
            "clock speed",
            "cpu",
            "processor",
            "cache hierarchy",
            "pipeline",
            "page table",
            "branch prediction",
            "thread scheduling",
            "virtual memory",
            "network latency",
        ]

        feedback = feedback.lower()

        for word in suspicious:
            if word in feedback and word not in corpus:
                return True

        return False

    def evaluate_answer(
        self,
        question,
        rubric,
        candidate_answer,
        question_type,
    ):

        system_prompt = (
            CODING_EVALUATION_PROMPT
            if question_type == "DSA_CODING"
            else THEORY_EVALUATION_PROMPT
        )

        prompt = f"""
    Interview Question

    {question}

    Evaluation Rubric

    {json.dumps(rubric, indent=2)}

    Candidate Answer

    {candidate_answer}

    {"Candidate submitted source code." if self._is_code_answer(candidate_answer) else ""}

    Return ONLY JSON

    {{
        "score":0,
        "verdict":"",

        "breakdown":{{}},

        "feedback":"",

        "strengths":[],

        "improvements":[],

        "missed_concepts":[]
    }}
    """

        try:
            result = self._json(
                system_prompt,
                prompt,
                eval=True,
            )

            if self._hallucinated(
                question,
                rubric,
                candidate_answer,
                result.get("feedback", ""),
            ):
                raise ValueError("Hallucinated evaluation.")

            return result

        except Exception as e:
            logger.warning(e)

            return {
                "score": 0,
                "verdict": "Needs Work",
                "breakdown": {},
                "feedback": "Evaluation failed.",
                "strengths": [],
                "improvements": [],
                "missed_concepts": [],
            }

    def get_embedding(
        self,
        text,
    ) -> Optional[list]:
        try:
            return self.embedding_model.encode(str(text)[:2048]).tolist()
        except Exception as e:
            logger.exception(e)
            return None

    def get_query_embedding(
        self,
        text,
    ):
        return self.get_embedding(text)
