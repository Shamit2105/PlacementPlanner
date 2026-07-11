# AI Architecture — Deep Dive Documentation

## Table of Contents
1. [System Overview](#1-system-overview)
2. [LLM Layer — `llm_service.py`](#2-llm-layer)
3. [Vector/Embedding Layer — `vector_service.py`](#3-vectorembedding-layer)
4. [Prompt Engineering — `prompts.py`](#4-prompt-engineering)
5. [AI Pipeline — Task Chain](#5-ai-pipeline--task-chain)
6. [Interview Evaluation Engine — `interviews/services.py`](#6-interview-evaluation-engine)
7. [Hyperparameter Decisions](#7-hyperparameter-decisions)
8. [Data Flow: End-to-End](#8-data-flow-end-to-end)

---

## 1. System Overview

The AI system in PlacementReady is a **multi-stage LLM + vector search pipeline**. It does four things:

| Stage | What | File |
|---|---|---|
| Extraction | Convert raw HTML interview experiences into structured JSON questions | `llm_service.py → extract_questions()` |
| Embedding | Convert question text into 384-dim float vectors | `llm_service.py → get_embedding()` |
| Deduplication | Find near-identical questions using cosine distance | `vector_service.py → find_duplicates()` |
| Evaluation | Score a candidate's live answer against a rubric | `llm_service.py → evaluate_answer()` |

**Why two models?**
- **Llama 4 Scout (via Groq)** — for text generation (fast, free-tier, good instruction following)
- **all-MiniLM-L6-v2 (local HuggingFace)** — for embeddings (runs on CPU, no API call needed)

---

## 2. LLM Layer

**File:** `backend/companies/llm_service.py`

### 2.1 Class Initialisation

```python
class LLMService:
    MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"
    EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
    _embedding_model = None   # class-level singleton

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
            LLMService._embedding_model = SentenceTransformer(self.EMBEDDING_MODEL)

        self.embedding_model = LLMService._embedding_model
```

**Why two separate `ChatGroq` instances (`generator` vs `evaluator`)?**

| Parameter | `generator` | `evaluator` |
|---|---|---|
| `temperature` | `0.2` | `0` |
| `max_tokens` | `4096` | `2048` |
| Purpose | Write answers, extract questions | Grade answers |

- `temperature=0.2` on the generator adds just enough randomness so that the model can creatively rephrase questions and write varied answers — pure greedy decoding (`temp=0`) makes answers repetitive.
- `temperature=0` on the evaluator forces **deterministic, reproducible scoring**. You don't want the score for the same answer to change between runs.
- `max_tokens=4096` for generation because a full coding answer (intuition + brute force + optimised + C++ code) can easily be 800+ words.
- `max_tokens=2048` for evaluation because the JSON rubric response is always short.

**Why `_embedding_model` as a class variable (singleton)?**

`SentenceTransformer` loads a ~22 MB model file from disk and keeps it in RAM. If you created a new `LLMService()` per Celery task and loaded the model each time, you'd pay a 2–3 second startup penalty per task and waste RAM. The class-level `None` check means the model is loaded **once** and reused across all task invocations in the same worker process.

---

### 2.2 Chain Invocation Pattern

```python
def _json(self, system_prompt, user_prompt, eval=False):
    chain = (
        ChatPromptTemplate.from_messages([
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ])
        | (self.evaluator if eval else self.generator)
        | self.json           # JsonOutputParser
    )
    return chain.invoke({})
```

This uses **LangChain's LCEL (LangChain Expression Language)** pipe `|` syntax.

**What each step does:**
1. `ChatPromptTemplate.from_messages(...)` — Formats a structured chat payload with a system role and a user role. System sets the persona/rules; User carries the actual data.
2. `| self.generator` — Sends the formatted messages to Groq's API. Returns a `AIMessage` object.
3. `| self.json` — `JsonOutputParser` strips markdown fences (` ```json ... ``` `), parses the string, returns a Python `dict` or `list`. If the model returns invalid JSON, it raises an exception which is caught upstream.

**Why `invoke({})` with empty dict?**

`ChatPromptTemplate` expects a dict of variables to fill into the template. Since variables are already embedded in the system/user strings before calling `_json`, there are no template variables left — so `{}` is correct.

---

### 2.3 `extract_questions()` and `format_questions()`

```python
def format_questions(self, raw_text: str, company: str = "") -> list[dict]:
    context = []
    if company:
        context.append(f"Company: {company}")
    prompt = "\n\n".join(context + [raw_text])
    questions = self.extract_questions(prompt)
    return self._normalize_questions(questions)
```

**Flow:**
1. Prepend company name to the raw scraped text (so the LLM can do company-specific filtering).
2. `extract_questions()` → calls `_json()` with `QUESTION_EXTRACTION_PROMPT` as system prompt.
3. LLM returns a JSON list of `{question, question_type}` objects.
4. `_normalize_questions()` validates and deduplicates the output.

**`_normalize_questions()` — Why it exists:**

LLMs can hallucinate invalid `question_type` values or return duplicates. This function:
- Checks `question_type` against `ALLOWED_QUESTION_TYPES` (set of enum values).
- Uses `re.sub(r"\s+", " ", question.lower())` to normalise whitespace before adding to a `seen` set → prevents near-identical phrasing from slipping through.

---

### 2.4 `generate_answer()`

```python
def generate_answer(self, question, question_type):
    prompt = f"""Question: {question}"""
    if question_type == "DSA_CODING":
        return self._text(CODING_ANSWER_PROMPT, prompt)
    return self._text(THEORY_ANSWER_PROMPT, prompt)
```

**Why two different answer prompts?**

- `DSA_CODING` → Uses `CODING_ANSWER_PROMPT` which forces: Intuition → Brute Force → Optimised → Time/Space Complexity → C++17 Code → Edge Cases. This is the **standard SWE interview answer format**.
- All other types (OS, DBMS, Networks, System Design) → Uses `THEORY_ANSWER_PROMPT` which forces: Definition → Explanation → Advantages → Limitations → Example. This matches how non-coding answers are expected in interviews.

**Why `_text()` (not `_json()`) here?**

Answers are free-form markdown text, not structured data. Asking the LLM to return markdown as JSON-encoded string adds unnecessary escaping and token overhead.

---

### 2.5 `generate_rubric()`

```python
def generate_rubric(self, question, question_type):
    try:
        return self._json(RUBRIC_PROMPT, prompt)
    except Exception:
        return {
            "algorithm": {"value": "", "weight": 40},
            "time_complexity": {"value": "", "weight": 15},
            "space_complexity": {"value": "", "weight": 10},
            ...
        }
```

**What is a rubric?**

A rubric is a structured scoring guide generated per-question. Example:
```json
{
  "algorithm": {"value": "Two-pointer", "weight": 40},
  "time_complexity": {"value": "O(n)", "weight": 15},
  "space_complexity": {"value": "O(1)", "weight": 10},
  "required_concepts": [{"name": "Sliding window", "weight": 20}],
  "edge_cases": ["Empty array", "All same elements"],
  "difficulty": "Medium"
}
```

**Why weights sum to 100?** The evaluator multiplies each dimension's score by its weight to compute a weighted total out of 10. This gives algorithmic correctness (40%) more importance than edge cases.

**Why have a fallback return?** If Groq's JSON output is malformed, the evaluator must still work — the fallback rubric gives empty strings so the LLM can still evaluate based on the question text alone.

---

### 2.6 `evaluate_answer()` — The Hallucination Guard

```python
def evaluate_answer(self, question, rubric, candidate_answer, question_type):
    ...
    result = self._json(system_prompt, prompt, eval=True)

    if self._hallucinated(question, rubric, candidate_answer, result.get("feedback", "")):
        raise ValueError("Hallucinated evaluation.")

    return result
```

**`_hallucinated()` — How it works:**

```python
def _hallucinated(self, question, rubric, candidate, feedback):
    corpus = (question + json.dumps(rubric) + candidate).lower()
    suspicious = ["clock speed", "cpu", "cache hierarchy", "pipeline", ...]
    feedback = feedback.lower()
    for word in suspicious:
        if word in feedback and word not in corpus:
            return True
    return False
```

**Why this guard?**

LLMs sometimes inject concepts from their training data that were never mentioned in the question or answer. For example, if the question is "explain bubble sort" and the model's feedback mentions "CPU cache hierarchy" (which wasn't in the question or the candidate's answer), that's a hallucination. The guard:
1. Builds a `corpus` = question + rubric + candidate answer (everything the model was *allowed* to know).
2. Checks suspicious hardware/systems terms in the feedback.
3. If a term appears in feedback but NOT in corpus → hallucination detected → raises exception → returns a safe fallback response.

---

### 2.7 `get_embedding()`

```python
def get_embedding(self, text) -> Optional[list]:
    try:
        return self.embedding_model.encode(str(text)[:2048]).tolist()
    except Exception:
        return None
```

**Why truncate to 2048 characters?**

`all-MiniLM-L6-v2` has a **maximum input of 256 tokens** (~1000–1500 characters). Feeding more than that causes silent truncation inside the model. The `:2048` slice is a safe upper bound to avoid feeding 10,000-character answers that waste time without improving the embedding quality.

**Why `.tolist()`?**

`encode()` returns a `numpy.ndarray`. PostgreSQL's pgvector extension and Django's `VectorField` expect a plain Python `list[float]`. `.tolist()` converts it.

---

## 3. Vector/Embedding Layer

**File:** `backend/companies/vector_service.py`

### 3.1 What Is a Vector Embedding?

A **vector embedding** converts text into a fixed-size list of floating-point numbers (a point in high-dimensional space). Semantically similar texts land **close together** in that space.

Example:
- "What is a hash map?" → `[0.12, -0.34, 0.78, ...]` (384 numbers)
- "Explain dictionary data structure" → `[0.11, -0.33, 0.76, ...]` (very close)
- "What is the TCP handshake?" → `[0.88, 0.22, -0.45, ...]` (far away)

**Model used:** `sentence-transformers/all-MiniLM-L6-v2`

- **384 dimensions** (confirmed by `VectorField(dimensions=384)` in `models.py`)
- **Why MiniLM?** It's a distilled model — 6 transformer layers instead of BERT's 12. Runs on CPU in ~5ms. Accuracy is close to full BERT for semantic similarity tasks. Perfect for a background Celery task.
- **Why not OpenAI's `text-embedding-3-small`?** It's a paid API. MiniLM runs locally at zero marginal cost per embedding.

---

### 3.2 `store_embedding()`

```python
def store_embedding(self, question_id: int, embedding: list[float]) -> bool:
    updated = Question.objects.filter(pk=question_id).update(
        embedding=embedding,
        status=ProcessingStatus.EMBEDDED,
    )
    return bool(updated)
```

**Why `.update()` instead of `.save()`?**

`.update()` issues a single `UPDATE` SQL statement without loading the object into Python memory. `.save()` would fetch the full Question row, modify it in Python, then save all fields — much more expensive for a hot loop of 50+ questions.

---

### 3.3 `semantic_search()`

```python
qs = (
    qs.annotate(distance=CosineDistance("embedding", query_embedding))
      .order_by("distance")
      [:limit]
)
```

**What SQL does this generate?**

```sql
SELECT *, embedding <=> '[0.12, -0.34, ...]'::vector AS distance
FROM companies_question
WHERE status = 'EMBEDDED' AND is_duplicate = FALSE AND embedding IS NOT NULL
ORDER BY distance ASC
LIMIT 10;
```

The `<=>` operator is pgvector's **cosine distance** operator.

**Cosine Distance vs Cosine Similarity:**

`cosine_distance = 1 - cosine_similarity`

- distance `0.0` → identical vectors (100% similar)
- distance `0.05` → 95% similar (near-duplicate)
- distance `0.35` → ~65% similar (related topic)
- distance `1.0` → completely unrelated

**Why cosine and not L2 (Euclidean) distance?**

`all-MiniLM-L6-v2` produces **unit-normalized** vectors (L2 norm = 1). For unit vectors, cosine similarity and dot product are equivalent. Cosine distance ignores vector magnitude and only cares about **direction** — that's exactly what we want for text similarity (a short question and a long question about the same topic should still be "similar").

---

### 3.4 `find_duplicates()` — Deduplication

```python
DUPLICATE_DISTANCE_THRESHOLD = 0.05

duplicates = (
    qs.annotate(distance=CosineDistance("embedding", embedding))
      .filter(distance__lt=DUPLICATE_DISTANCE_THRESHOLD)
      .order_by("distance")
)
```

**Why `0.05` as the threshold?**

- `distance < 0.05` means `cosine_similarity > 0.95`.
- At 0.95 similarity, two questions are essentially the same question phrased slightly differently.
- Testing showed that `0.05` correctly catches paraphrases like "What is a binary search tree?" and "Explain BST with properties" while not falsely flagging "What is BFS?" and "What is DFS?" (which are related but distinct).

**Why not use exact text matching instead?**

Exact string matching misses paraphrases. "Explain merge sort" and "How does merge sort work?" are duplicates semantically but different strings.

---

### 3.5 `get_interview_question_set()` — Smart Question Selection

```python
per_type = max(1, total_questions // len(question_types))
all_ids = []

for qtype in question_types:
    results = self.semantic_search(
        query_embedding=query_embedding,
        question_type=qtype,
        company_slug=company_slug,
        limit=per_type + 2,
    )
    all_ids.extend([q.pk for q in results[:per_type]])
```

**What is the query embedding here?**

The calling code passes an embedding of a string like `"Amazon DSA_CODING SYSTEM_DESIGN"`. The semantic search then finds questions that are closest to that combined intent.

**Why `per_type + 2` in the limit?**

Fetching 2 extra gives a small buffer to handle edge cases where a question appears across type buckets. The final `unique_ids = list(dict.fromkeys(all_ids))[:total_questions]` deduplicates and trims.

---

## 4. Prompt Engineering

**File:** `backend/companies/prompts.py`

### 4.1 `QUESTION_EXTRACTION_PROMPT`

```
You are an expert technical interviewer.
Extract only technical interview questions...
Return ONLY valid JSON.
Format: [{"question":"","question_type":""}]
Allowed question_type values: DSA_CODING, DSA_THEORY, OS, DBMS, NETWORKS, SYSTEM_DESIGN
Rules:
• Keep only coding, core CS theory...
• For DSA_CODING, include one short sample testcase inside the question text.
• Never invent questions.
• Never generate answers.
```

**Why "Return ONLY valid JSON"?**

LLMs tend to prefix their output with explanations like "Here is the JSON:". `JsonOutputParser` can strip markdown fences but gets confused by leading prose. The hard instruction eliminates this.

**Why "Never invent questions"?**

Without this, the model will hallucinate questions that were not in the input text. Since we're building a question bank from real interview experiences, invented questions have no source attribution and may be wrong.

**Why include a sample testcase for DSA_CODING?**

During evaluation, the rubric checker can verify if the candidate's code handles the testcase. It also makes the question self-contained — the candidate doesn't need external context.

### 4.2 `RUBRIC_PROMPT`

The rubric weights are hardcoded in the prompt:
```
"algorithm": {"weight": 40}
"time_complexity": {"weight": 15}
"space_complexity": {"weight": 10}
```

**Why these weights?**

In real SWE interviews (especially at FAANG):
- Getting the **right algorithm** is the most critical (40%). An O(n²) brute force when O(n log n) is expected is a failure.
- **Time complexity** analysis (15%) matters because interviewers always ask "what's your complexity?"
- **Space complexity** (10%) is secondary to time complexity in most problems.
- The remaining 35% is allocated to `required_concepts` which the LLM fills based on the specific question (e.g., "understands two-pointer technique").

### 4.3 `CODING_EVALUATION_PROMPT` — The "Use ONLY" Rule

```
Use ONLY
Question
Rubric
Candidate Answer
Never introduce concepts outside them.
```

This is the most important constraint. It pairs with the `_hallucinated()` guard in `llm_service.py`. The prompt-level instruction reduces hallucination frequency; the code-level guard catches any that slip through.

---

## 5. AI Pipeline — Task Chain

**File:** `backend/companies/tasks.py`

The pipeline is a **chain of Celery tasks** triggered sequentially:

```
scrape_and_ingest_questions
        ↓
compute_and_store_embedding  (one per question, staggered)
        ↓
    [if duplicate]  → flag is_duplicate = True, STOP
    [if unique]     → process_single_question
                              ↓
                    generate_answer + generate_rubric
                              ↓
                    status = PROCESSED (ready for interviews)
```

### 5.1 `scrape_and_ingest_questions`

```python
@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=120,
    rate_limit="10/m",
    name="questions.scrape_and_ingest",
)
```

**Parameter explanations:**

| Parameter | Value | Why |
|---|---|---|
| `bind=True` | — | Gives access to `self` so you can call `self.retry()` |
| `max_retries=3` | 3 | Scraping can fail due to network timeouts; 3 attempts is a reasonable retry budget |
| `default_retry_delay=120` | 120s | Wait 2 minutes before retrying to respect the Serper API rate limit |
| `rate_limit="10/m"` | 10 per minute | Serper's free tier allows ~10 searches/minute |

**Staggered embedding triggers:**
```python
for i, qid in enumerate(saved_ids):
    compute_and_store_embedding.apply_async(args=[qid], countdown=i * 5)
```

Each embedding task is delayed by `i * 5` seconds (0s, 5s, 10s, 15s...). This prevents all embedding tasks from hitting the embedding model simultaneously, which could cause CPU spikes on low-resource VMs.

### 5.2 `compute_and_store_embedding`

```python
@shared_task(bind=True, max_retries=3, name="questions.compute_embedding")
def compute_and_store_embedding(self, question_id: int):
    q = Question.objects.get(pk=question_id, status=ProcessingStatus.SCRAPED)
    embedding = llm.get_embedding(text_to_embed)
    vs.store_embedding(question_id, embedding)

    duplicates = vs.find_duplicates(embedding=embedding, exclude_id=question_id)
    if duplicates.exists():
        q.is_duplicate = True
        q.status = ProcessingStatus.PROCESSED
        q.save(update_fields=["is_duplicate", "status"])
    else:
        q.status = ProcessingStatus.EMBEDDED
        q.save(update_fields=["status"])
        process_single_question.apply_async(args=[question_id])
```

**Status state machine:**

```
SCRAPED → (embedding computed) → EMBEDDED → (answer generated) → PROCESSED
                                    ↓
                              (duplicate found) → PROCESSED (is_duplicate=True)
                                    ↓
                              (any failure) → FAILED
```

**Why check for duplicates immediately after embedding?**

It prevents wasting an LLM API call (answer generation + rubric generation) on a question that is semantically identical to one already in the bank. Answer generation costs tokens; skipping it for duplicates saves money and time.

### 5.3 `process_single_question`

```python
interview_a = llm.generate_answer(q.interview_question, q.question_type)
rubric = llm.generate_evaluation_rubric(q.interview_question, q.question_type)
q.interview_answer = interview_a
q.evaluation_rubric = rubric
q.status = ProcessingStatus.PROCESSED
q.save(update_fields=["interview_answer", "evaluation_rubric", "status", "error_log"])
time.sleep(1.5)
```

**Why `time.sleep(1.5)` between calls?**

Groq's free tier has rate limits. Generating answer and rubric in rapid succession for many questions in parallel would hit `429 Too Many Requests`. The 1.5s sleep is a conservative politeness delay. In production with a paid Groq key, this can be removed.

---

## 6. Interview Evaluation Engine

**File:** `backend/interviews/services.py` + `backend/interviews/tasks.py`

### 6.1 Adaptive Difficulty — `select_questions()`

```python
if interview_q.score >= 7:
    if current_difficulty == "EASY":   next_difficulty = "MEDIUM"
    elif current_difficulty == "MEDIUM": next_difficulty = "HARD"
else:
    next_difficulty = current_difficulty  # stay on same level
```

**Why threshold of 7/10?**

A score of 7+ means the candidate demonstrated solid understanding. At 5–6 they got the gist but missed details — staying at the same difficulty gives them more practice. Below 5 they struggled — no point increasing difficulty. This mimics how real interviewers adapt question difficulty mid-interview.

### 6.2 `normalize_verdict()`

```python
def normalize_verdict(verdict, score) -> str:
    normalized = str(verdict or "").strip().lower()
    if normalized in {"strong", "acceptable", "needs work"}:
        return normalized.title()
    # fallback: derive from numeric score
    if float(score) >= 8: return "Strong"
    if float(score) >= 5: return "Acceptable"
    return "Needs Work"
```

**Why two paths?**

The LLM is instructed to return a `verdict` string. But LLMs sometimes return "Good", "Poor", "Pass", etc. The primary path normalises known values. The secondary path converts the numeric score into a verdict — guaranteeing the field is always one of the three valid enum values that the frontend expects.

### 6.3 Session Evaluation — `evaluate_session_answers` (Celery task)

This task fires **after the session is marked COMPLETED**. It:
1. Loops all `ANSWERED` InterviewQuestions in the session.
2. Generates a reference answer if the question doesn't have one (edge case for LLM-generated questions that skipped `process_single_question`).
3. Calls `llm.evaluate_answer()` with question + rubric + candidate answer.
4. Recalculates `session.total_score = average(all scores)`.

**Why run this as a Celery task and not synchronously?**

Evaluating 10 questions sequentially with LLM calls takes 15–30 seconds. Doing this in the HTTP request handler would timeout the frontend. Celery runs it in the background; the frontend polls or gets notified when done.

---

## 7. Hyperparameter Decisions

| Hyperparameter | Value | File | Reason |
|---|---|---|---|
| `temperature` (generator) | `0.2` | `llm_service.py` | Low but non-zero: creative enough to paraphrase, deterministic enough to be consistent |
| `temperature` (evaluator) | `0` | `llm_service.py` | Fully deterministic scoring — same answer always gets same score |
| `max_tokens` (generator) | `4096` | `llm_service.py` | Full coding answer needs ~600-800 tokens; 4096 is safe headroom |
| `max_tokens` (evaluator) | `2048` | `llm_service.py` | JSON rubric response is short; 2048 is 2x overkill = safety |
| Embedding dimensions | `384` | `models.py` | MiniLM-L6-v2 native output size |
| Embedding truncation | `2048 chars` | `llm_service.py` | MiniLM max is ~256 tokens; 2048 chars ≈ 400 tokens (safe upper bound) |
| Duplicate threshold | `0.05` | `vector_service.py` | Cosine distance < 0.05 = similarity > 95% = almost identical text |
| Related threshold | `0.35` | `vector_service.py` | Distance < 0.35 = similarity > 65% = same topic area |
| Embedding countdown stagger | `i * 5` seconds | `tasks.py` | Avoids CPU spike from concurrent embedding |
| LLM sleep between calls | `1.5s` | `tasks.py` | Groq free-tier rate limit compliance |
| Retry delay | `120s` | `tasks.py` | 2min cooldown respects Serper API limits |
| Max retries | `3` | `tasks.py` | Beyond 3 failures on one question = likely a persistent error, stop trying |
| `per_type + 2` buffer | `+2` | `vector_service.py` | Small buffer so deduplication doesn't leave question type under-represented |
| Score threshold for "Strong" | `>= 8` | `services.py` | Industry norm: 8/10 = strong pass in structured interviews |
| Score threshold for "Acceptable" | `>= 5` | `services.py` | 5/10 = partial credit; candidate understood the concept but missed key details |

---

## 8. Data Flow: End-to-End

```
User calls POST /api/questions/scrape/
        ↓
scrape_and_ingest_questions.delay(company_name="Amazon", question_type="DSA_CODING")
        ↓
QuestionScraper.scrape_experiences()   ← fetches URLs from Serper, HTML from GFG/LC
        ↓
LLMService.format_questions(raw_text)  ← Llama extracts [{question, question_type}]
        ↓
Question.objects.create(status=SCRAPED)
        ↓
compute_and_store_embedding.apply_async(args=[q.pk], countdown=i*5)
        ↓
LLMService.get_embedding(question_text)  ← MiniLM → [384 floats]
        ↓
VectorService.store_embedding(q.pk, embedding)  ← saved to pgvector
        ↓
VectorService.find_duplicates(embedding)
    → duplicate? → q.is_duplicate=True, STOP
    → unique?    → process_single_question.apply_async(q.pk)
                          ↓
                  LLMService.generate_answer()  ← Llama writes reference answer
                  LLMService.generate_rubric()  ← Llama creates scoring rubric
                  q.status = PROCESSED
                          ↓
        Question is now ready for mock interviews

User starts interview → InterviewService.select_questions()
        ↓
User answers → LLMService.evaluate_answer(question, rubric, candidate_answer)
        ↓
Score (0-10) + verdict + feedback returned immediately
        ↓
Session ends → evaluate_session_answers.delay(session_id)  ← final aggregation
```
