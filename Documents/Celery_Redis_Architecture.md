# Celery & Redis Architecture — Deep Dive Documentation

## Table of Contents
1. [Why Celery + Redis Exist Here](#1-why-celery--redis-exist-here)
2. [How Redis Works as a Message Broker](#2-how-redis-works-as-a-message-broker)
3. [How Celery Works — Core Concepts](#3-how-celery-works--core-concepts)
4. [Project Configuration](#4-project-configuration)
5. [Task Definitions — Every Decorator Explained](#5-task-definitions--every-decorator-explained)
6. [Task Chaining Pattern Used Here](#6-task-chaining-pattern-used-here)
7. [Docker Setup](#7-docker-setup)
8. [Retry Logic — Deep Dive](#8-retry-logic--deep-dive)
9. [Rate Limiting](#9-rate-limiting)
10. [Why Not Use Django Signals or Threads Instead](#10-why-not-use-django-signals-or-threads-instead)

---

## 1. Why Celery + Redis Exist Here

The core problem: **LLM API calls are slow** (1–10 seconds each). If these ran inside a Django view:

```
User clicks "Scrape Questions" → HTTP request sits open for 3 minutes → Browser times out
```

Celery solves this by **decoupling work from the HTTP request**:

```
User clicks "Scrape Questions"
    → Django creates a Celery task (takes 1ms)
    → Returns HTTP 200 immediately
    → Celery worker runs the 3-minute job in the background
```

**Three slow operations that must be async:**
| Operation | Time per item | Why slow |
|---|---|---|
| Scraping + LLM question extraction | 5–30s per page | HTTP fetch + Groq API call |
| Embedding computation | ~50ms per question | MiniLM model inference |
| Answer + rubric generation | 3–8s per question | Two sequential Groq API calls |

Running these in a Django view would block the entire web process. With Celery, they run in a **separate worker process** and the web server is free to handle other requests.

---

## 2. How Redis Works as a Message Broker

### What is a Message Broker?

A message broker is a **middleman** that holds tasks until a worker is ready to process them. Think of it as a post office:
- Django (producer) drops a letter (task) in the mailbox (Redis queue)
- Celery worker (consumer) picks letters from the mailbox and processes them

### Redis Data Structure Used

Redis stores Celery tasks as **items in a List** (Redis's linked list data type):

```
Redis Key: "celery"  (the default queue name)
Value Type: LIST

RPUSH celery '{"task": "questions.scrape_and_ingest", "args": [], "kwargs": {"company_name": "Amazon"}}'
RPUSH celery '{"task": "questions.compute_embedding", "args": [42], "kwargs": {}}'

Worker does:
BLPOP celery 0   ← blocking left-pop: waits until an item appears, then takes it
```

- `RPUSH` = push to the **right** (end of queue) — producer adds tasks
- `BLPOP` = blocking **left** pop — worker waits and takes from front of queue
- This gives **FIFO** (First In, First Out) ordering

### Why Redis (not RabbitMQ)?

| Feature | Redis | RabbitMQ |
|---|---|---|
| Setup | `docker run redis` — zero config | Requires exchange/queue/binding setup |
| Persistence | Optional (RDB snapshots) | Yes (message durability built-in) |
| Memory | In-memory (fast) | Disk-backed (slower but safer) |
| Result backend | Yes (same Redis instance) | Needs separate backend |
| Free tier | Redis Cloud free tier | CloudAMQP free tier (limited) |

For this project, task durability (surviving Redis restart) is not critical — a lost scraping task just means re-triggering it. Redis's simplicity wins.

### Redis as Result Backend

```python
# settings.py
CELERY_BROKER_URL = os.environ.get('REDIS_URL', 'redis://redis:6379/0')
CELERY_RESULT_BACKEND = CELERY_BROKER_URL   # same Redis instance for results
```

When a task completes, Celery stores its return value in Redis:
```
Key: "celery-task-meta-<task-uuid>"
Value: {"status": "SUCCESS", "result": {"saved": 15, "skipped": 3}, "traceback": null}
TTL: 86400s (1 day, default)
```

The `/0` in `redis://redis:6379/0` means **database 0**. Redis has 16 logical databases (0–15). Using db 0 for both broker and backend is fine for this project size.

---

## 3. How Celery Works — Core Concepts

### Worker Process Model

```
celery -A PlacementReady worker -l info --concurrency=2
```

This starts **one Celery worker** with **2 child processes** (prefork model):

```
celery worker (supervisor)
    ├── child process 1  ← picks task from Redis queue, runs it
    └── child process 2  ← picks task from Redis queue, runs it
```

`--concurrency=2` means at most 2 tasks run simultaneously. Why 2 (not 4 or 8)?

- Each child loads `SentenceTransformer` into RAM (~50MB)
- Each child makes concurrent Groq API calls
- With 2 workers, RAM stays ~200MB total — safe for a small VM/container
- More concurrency + rate-limited Groq API = more 429 errors, not more throughput

### Task Serialisation

```python
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
```

Tasks are serialised to JSON before being pushed to Redis. This means task arguments must be JSON-serialisable (strings, ints, lists, dicts — no Django model instances). That's why tasks accept `question_id: int` instead of `question: Question`.

---

## 4. Project Configuration

### `PlacementReady/celery.py`

```python
import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'PlacementReady.settings')

app = Celery('PlacementReady')

app.config_from_object('django.conf:settings', namespace='CELERY')

app.autodiscover_tasks()
```

**Line-by-line explanation:**

`os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'PlacementReady.settings')`
— Celery workers are separate processes that don't inherit the web server's environment. This ensures `settings.py` is loaded when the worker starts.

`app = Celery('PlacementReady')`
— Creates the Celery application. The string `'PlacementReady'` is just a name for logging.

`app.config_from_object('django.conf:settings', namespace='CELERY')`
— Reads all `settings.py` keys that start with `CELERY_` and uses them as Celery config. This avoids maintaining a separate Celery config file.

`app.autodiscover_tasks()`
— Scans all `INSTALLED_APPS` for a `tasks.py` file and imports it. This is how `@shared_task` decorated functions in `companies/tasks.py` and `interviews/tasks.py` get registered.

### `PlacementReady/__init__.py`

```python
from .celery import app as celery_app
__all__ = ('celery_app',)
```

This import ensures the Celery app is created when Django starts. Without it, `@shared_task` decorators would fail because the Celery app wouldn't exist yet when `tasks.py` is imported.

### `settings.py` — All Celery Settings Explained

```python
CELERY_BROKER_URL = os.environ.get('REDIS_URL', 'redis://redis:6379/0')
```
URL format: `redis://[password@]host:port/db_number`. `redis` is the Docker service name (resolved by Docker's internal DNS to the Redis container's IP).

```python
CELERY_RESULT_BACKEND = CELERY_BROKER_URL
```
Store task results in the same Redis. If you never `.get()` task results, you can set this to `None` to save memory.

```python
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
```
Only accept and send JSON payloads. The old default was `pickle` which is a security risk (arbitrary code execution if an attacker controls the broker).

---

## 5. Task Definitions — Every Decorator Explained

### `@shared_task` vs `@app.task`

```python
from celery import shared_task

@shared_task(bind=True, max_retries=3, ...)
def scrape_and_ingest_questions(self, ...):
    ...
```

`@shared_task` is used in reusable apps (like `companies`, `interviews`) because the task doesn't need a reference to the specific Celery app instance. It binds to whatever Celery app is active at runtime. `@app.task` would require importing the `app` object from `PlacementReady/celery.py`, creating a circular import.

### `bind=True`

Injects `self` as the first argument — a reference to the task instance. Required to call `self.retry()`. Without `bind=True`, you have no handle to retry the task from within itself.

```python
# With bind=True:
def scrape_and_ingest_questions(self, company_name):
    try:
        ...
    except Exception as exc:
        raise self.retry(exc=exc)   # ← needs self
```

### `max_retries=3`

Maximum number of automatic retries. After 3 failures, Celery marks the task as `FAILURE` and stops retrying. The exception is logged but not re-raised to the caller.

### `default_retry_delay=120`

Seconds to wait before the next retry attempt. 120 seconds (2 minutes) is chosen because:
- Scraper failures are usually rate-limit related (Serper 429s)
- 2 minutes gives the rate limit window time to reset
- Shorter delays (10–30s) would just hit the same rate limit again

### `rate_limit="10/m"`

Celery-level rate limiting: this worker will process at most 10 instances of this task per minute **across all workers**. This is enforced via Redis counters. Matches Serper's free-tier limit.

### `name="questions.scrape_and_ingest"`

Explicit task name. Without this, Celery uses the Python module path: `companies.tasks.scrape_and_ingest_questions`. Explicit names:
- Are shorter in logs
- Don't break if you rename the function or move the file
- Make the Flower monitoring dashboard readable

---

## 6. Task Chaining Pattern Used Here

This project uses **manual chaining** (not Celery's built-in `chain()` or `chord()`):

```python
# In scrape_and_ingest_questions:
for i, qid in enumerate(saved_ids):
    compute_and_store_embedding.apply_async(args=[qid], countdown=i * 5)

# In compute_and_store_embedding:
if unique:
    process_single_question.apply_async(args=[question_id])
```

**Why manual chaining instead of `chain(task1, task2, task3)`?**

Celery's `chain()` is elegant but requires knowing the next task's arguments at the time the chain is created. Here, `process_single_question` only runs if the question is **not** a duplicate — a condition known only after `compute_and_store_embedding` runs. Manual chaining handles this conditional branching cleanly.

### `apply_async` vs `delay`

```python
# These are equivalent:
compute_and_store_embedding.delay(question_id)
compute_and_store_embedding.apply_async(args=[question_id])

# apply_async also accepts options:
compute_and_store_embedding.apply_async(args=[question_id], countdown=30)
```

`delay(*args, **kwargs)` is syntactic sugar for `apply_async(args, kwargs)`. Use `apply_async` when you need extra options like `countdown`, `eta`, or `queue`.

### `countdown=i * 5` — Staggered Execution

```python
for i, qid in enumerate(saved_ids):
    compute_and_store_embedding.apply_async(args=[qid], countdown=i * 5)
```

For 10 questions, tasks fire at: 0s, 5s, 10s, 15s, 20s, 25s, 30s, 35s, 40s, 45s.

This staggers the load instead of firing all 10 simultaneously. With `--concurrency=2`, only 2 run at once anyway, but the countdown prevents all 10 from sitting in the "ready" queue simultaneously and avoids thundering-herd on the embedding model.

### `evaluate_session_answers.delay(session.id)`

```python
# In interviews/views.py:
if pending_count == 0:
    session.status = InterviewSession.SessionStatus.COMPLETED
    session.save()
    evaluate_session_answers.delay(session.id)
```

This fires after all questions in an interview session are answered. It runs asynchronously so the `end_session` API response is instant — the user doesn't wait for LLM evaluation.

---

## 7. Docker Setup

```yaml
# docker-compose.yml
services:
  redis:
    image: redis:7-alpine
    container_name: placement_redis
    restart: always
    ports:
      - "6378:6379"    # host:container

  web:
    build: .
    command: python manage.py runserver 0.0.0.0:8000
    depends_on:
      - redis

  celery:
    build: .
    command: celery -A PlacementReady worker -l info --concurrency=2
    depends_on:
      - redis
```

**Why `redis:7-alpine`?**

Alpine Linux base image. Redis 7 is ~10MB vs Redis 7 on Debian (~120MB). No functional difference for this use case.

**Why `6378:6379` (not `6379:6379`)?**

Port 6379 might be occupied by a local Redis installation on the developer's machine. Mapping to host port 6378 avoids conflicts. Inside Docker, services still communicate on port 6379 (container port).

**Why `depends_on: redis`?**

The Django web and Celery containers need Redis to be up before they start. `depends_on` ensures Docker starts Redis first. Note: `depends_on` only waits for the container to **start**, not for Redis to be **ready** to accept connections. For production, use a healthcheck.

**Why same Docker image for `web` and `celery`?**

Both need the same Python environment (Django, Celery, all pip packages). Using one image keeps the build simple. The only difference is the `command` — `runserver` vs `celery worker`.

**Why `restart: always` only on Redis?**

Redis must always be up for Celery to function. If Redis crashes, the web and Celery containers will also fail. Redis gets `restart: always`; the app containers can be restarted manually (or given `restart: on-failure` in production).

---

## 8. Retry Logic — Deep Dive

```python
@shared_task(bind=True, max_retries=3, default_retry_delay=120)
def scrape_and_ingest_questions(self, ...):
    try:
        experiences = scraper.scrape_experiences(...)
    except Exception as exc:
        raise self.retry(exc=exc)
```

### How `self.retry()` works

1. Increments the retry counter (stored on the task instance)
2. If `retries < max_retries`: re-queues the task with a `countdown` delay, then raises `Retry` exception (which Celery catches internally)
3. If `retries >= max_retries`: raises the original `exc`, marking the task as `FAILURE`

**Why `raise self.retry(exc=exc)` (not just `self.retry(exc=exc)`)?**

`self.retry()` raises a `celery.exceptions.Retry` exception internally. But type checkers don't know this — they think execution continues after `self.retry()`. Using `raise self.retry()` makes the control flow explicit to both the programmer and the type checker. Functionally identical.

### Per-task retry configuration

```python
# scrape_and_ingest_questions: max_retries=3, delay=120s
# compute_and_store_embedding: max_retries=3 (no delay = uses default 180s)
# process_single_question:     max_retries=3 (no delay)
# generate_questions_via_llm:  max_retries=2, delay=30s
```

`generate_questions_via_llm` has `max_retries=2` and `delay=30s` because it's a supplementary task (runs when scraping yields too few questions). Shorter budget since it's less critical.

---

## 9. Rate Limiting

### Task-level rate limit

```python
@shared_task(rate_limit="10/m", ...)
def scrape_and_ingest_questions(self, ...):
```

Celery uses Redis to track how many times this task has been executed in the current minute window. If the limit is reached, the task is held in the queue until the window resets.

**Format:** `"N/period"` where period is `s` (second), `m` (minute), `h` (hour).

### Application-level sleep

```python
time.sleep(1.5)   # in process_single_question
```

This is a manual rate limit inside the task body — not Celery's built-in rate limiting. It ensures that even within a single task execution, consecutive Groq API calls are spaced 1.5 seconds apart.

### Why both?

- `rate_limit="10/m"` limits **how often the task itself is started** (queue-level)
- `time.sleep(1.5)` limits **calls within a single task execution** (execution-level)

They operate at different granularities and both are needed.

---

## 10. Why Not Use Django Signals or Threads Instead?

### Why not Django Signals?

```python
# A tempting but wrong approach:
@receiver(post_save, sender=Question)
def trigger_embedding(sender, instance, created, **kwargs):
    if created:
        compute_embedding(instance.pk)   # runs synchronously in the request!
```

Django signals run **synchronously in the same thread** as the request. `compute_embedding` would block the HTTP response for several seconds per question. Signals are for lightweight side-effects (invalidating cache, sending a notification), not heavy computation.

### Why not Python threads?

```python
import threading

def handle_scrape(request):
    t = threading.Thread(target=scrape_and_process, args=[company])
    t.start()
    return Response({"status": "started"})
```

Problems with threads:
1. **Django's ORM is not thread-safe** without careful connection management. Each thread needs its own DB connection, and unclosed connections cause leaks.
2. **No retry logic** — if the thread crashes, the work is lost silently.
3. **No monitoring** — no way to see running/failed tasks, no admin UI.
4. **No rate limiting** — threads would hammer the Groq API.
5. **No persistence** — if the Django process restarts, all in-flight threads die.

### Celery wins because:

| Feature | Django Thread | Celery + Redis |
|---|---|---|
| Survives Django restart | ❌ | ✅ (task stays in Redis) |
| Retry on failure | ❌ | ✅ (`max_retries`) |
| Rate limiting | ❌ | ✅ (`rate_limit`) |
| Monitoring UI | ❌ | ✅ (Flower) |
| ORM safe | ⚠️ (fragile) | ✅ (each worker has own connection) |
| Distributed (multi-server) | ❌ | ✅ |

---

## Summary: Full Lifecycle of One Task

```
1. Django view calls:
   scrape_and_ingest_questions.delay(company_name="Amazon", question_type="DSA_CODING")

2. Celery serialises the call to JSON:
   {"task": "questions.scrape_and_ingest", "kwargs": {"company_name": "Amazon", ...}}

3. Celery pushes to Redis:
   RPUSH celery '{"task": "questions.scrape_and_ingest", ...}'

4. Django returns HTTP 202 immediately. User is not waiting.

5. Celery worker (child process) does:
   BLPOP celery 0   → gets the task JSON

6. Worker deserialises JSON → calls scrape_and_ingest_questions(company_name="Amazon", ...)

7. Task runs (5–30s):
   - Scraper fetches 8 pages from GFG/LeetCode
   - LLM extracts questions from each page
   - Questions saved to PostgreSQL with status=SCRAPED

8. Task queues embedding tasks (staggered):
   RPUSH celery '{"task": "questions.compute_embedding", "args": [101], "eta": now+0s}'
   RPUSH celery '{"task": "questions.compute_embedding", "args": [102], "eta": now+5s}'
   ...

9. Each embedding task:
   - MiniLM encodes question text → [384 floats]
   - Saved to PostgreSQL VectorField via pgvector
   - Cosine similarity check → duplicate? → stop
   - Unique? → queue process_single_question

10. process_single_question:
    - Groq API: generate reference answer
    - Groq API: generate evaluation rubric
    - status = PROCESSED
    - Question is ready for mock interviews

Total time: ~2-5 minutes for 10 questions, all async.
Django web process was never blocked.
```
