# Scraper Architecture — Deep Dive Documentation

## Table of Contents
1. [Overview](#1-overview)
2. [Three-Layer Architecture](#2-three-layer-architecture)
3. [`SearchClient` — Google via Serper](#3-searchclient--google-via-serper)
4. [`PageFetcher` — HTML & GraphQL Fetching](#4-pagefetcher--html--graphql-fetching)
5. [`TextCleaner` — Noise Removal](#5-textcleaner--noise-removal)
6. [`QuestionScraper` — Orchestrator](#6-questionscraper--orchestrator)
7. [Standalone Script — `serper_scrap.py`](#7-standalone-script--serper_scrapypy)
8. [Constants & Why They Matter](#8-constants--why-they-matter)
9. [Full Data Flow](#9-full-data-flow)
10. [Error Handling Strategy](#10-error-handling-strategy)

---

## 1. Overview

The scraper answers a single question: **"Given a company name and question type, fetch real interview experiences from the web and return clean text."**

It is intentionally **stateless** — it takes inputs, fetches, cleans, and returns. Persistence is handled by the Celery task that calls it.

**Sources targeted (why only two):**

| Source | Why |
|---|---|
| `leetcode.com/discuss` | Largest repository of recent interview experiences (2022–2026); candidates post full round-by-round experiences with actual questions |
| `geeksforgeeks.org` | Structured interview experience articles; GFG editors enforce a consistent format with question lists |

Other sources (Glassdoor, AmbitionBox, LinkedIn) were rejected because:
- They require login/Cloudflare bypass (too brittle)
- Their content is unstructured testimonials, not question lists
- Terms of Service explicitly prohibit scraping

---

## 2. Three-Layer Architecture

```
┌─────────────────────────────────────────────────────┐
│               QuestionScraper (orchestrator)         │
│   - Builds search queries                            │
│   - Coordinates SearchClient + PageFetcher           │
│   - Fingerprints pages to avoid duplicate fetches    │
└──────────────────┬──────────────────┬───────────────┘
                   │                  │
        ┌──────────▼──────┐  ┌────────▼────────┐
        │  SearchClient   │  │   PageFetcher   │
        │  (Serper API)   │  │  (HTTP/GraphQL) │
        └──────────┬──────┘  └────────┬────────┘
                   │                  │
                   └────────┬─────────┘
                            │
                   ┌────────▼────────┐
                   │   TextCleaner   │
                   │  (noise removal)│
                   └─────────────────┘
```

---

## 3. `SearchClient` — Google via Serper

**File:** `backend/companies/scraper.py`

```python
SERPER_URL = "https://google.serper.dev/search"

class SearchClient:
    def __init__(self):
        self.api_key = settings.SERPER_API_KEY

    def search(self, query: str, num: int = 10) -> list[dict]:
        response = requests.post(
            SERPER_URL,
            headers={
                "X-API-KEY": self.api_key,
                "Content-Type": "application/json",
            },
            json={"q": query, "num": num},
            timeout=10,
        )
        response.raise_for_status()
        return response.json().get("organic", [])
```

### What is Serper?

Serper is a Google Search API proxy. It sends queries to Google and returns structured JSON results. The `organic` key contains the actual search results (not ads).

**Why Serper instead of Google's official Custom Search API?**

| | Serper | Google CSE |
|---|---|---|
| Free tier | 2500 queries/month | 100 queries/day |
| Latency | ~200ms | ~400ms |
| Result quality | Full Google results | Limited to configured sites |
| Setup | API key only | Complex configuration |

**Why `requests.post` instead of `requests.get`?**

Serper uses a POST-based API design. The query goes in the JSON body (`{"q": query, "num": num}`) rather than URL query params. This allows richer query objects in the future (e.g., `location`, `hl`, `gl` filters).

**Why `timeout=10`?**

If Serper is slow or down, `requests` will hang forever without a timeout, blocking the Celery worker. 10 seconds is generous enough for a normal response but short enough to not hold up the task queue.

**Why return `[]` on exception?**

The orchestrator loops over results; returning `[]` means the loop body simply never executes. The task continues with whatever experiences were already gathered. This makes the scraper **fault-tolerant** — a Serper outage doesn't crash the entire task.

---

## 4. `PageFetcher` — HTML & GraphQL Fetching

```python
class PageFetcher:
    USER_AGENT = (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/125.0 Safari/537.36"
    )

    def fetch_text(self, url: str) -> str:
        if "leetcode.com" in url:
            return self._fetch_leetcode_text(url)
        return self._fetch_html_text(url)
```

### 4.1 Routing Logic — Why LeetCode Gets Special Treatment

LeetCode's discuss pages are **React Single Page Applications**. A standard `requests.get()` returns the shell HTML with no content — the actual post text is loaded via JavaScript XHR calls. `requests` does not execute JavaScript.

**Solution:** LeetCode exposes a **GraphQL API** at `https://leetcode.com/graphql` that returns the post content as JSON directly. This bypasses the SPA entirely.

### 4.2 `_fetch_html_text()` — For GFG

```python
def _fetch_html_text(self, url: str) -> str:
    response = requests.get(
        url,
        headers={"User-Agent": self.USER_AGENT},
        timeout=15,
    )
    response.raise_for_status()
    time.sleep(PAGE_FETCH_SLEEP)   # PAGE_FETCH_SLEEP = 1.5

    soup = BeautifulSoup(response.text, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
        tag.decompose()

    article = soup.select_one(
        "article, main, div.entry-content, div[class*='article']"
    )
    text = article.get_text("\n", strip=True) if article else soup.get_text("\n", strip=True)
    return TextCleaner.clean(text)
```

**Why `User-Agent` header?**

GFG and most modern sites reject requests without a browser-like User-Agent (returning 403). The UA string mimics Chrome 125 on Linux — realistic enough to pass basic bot detection.

**Why `timeout=15` (vs 10 for Serper)?**

GFG pages are heavier than API calls (full HTML, images referenced). 15 seconds allows for slow connections without blocking forever.

**Why `time.sleep(PAGE_FETCH_SLEEP)` (1.5s)?**

Without a delay between requests, sending 8 sequential GFG requests in ~2 seconds looks like a DDoS and triggers rate limiting (HTTP 429). The 1.5s pause makes the pattern look like a human reading pages.

**Why strip `script`, `style`, `nav`, `footer`, `header`, `aside` tags?**

- `script`/`style` — JavaScript code and CSS that would pollute the text with code
- `nav` — Navigation menus ("Home > Companies > Google")
- `footer` — Copyright notices, social links
- `header` — Site logo, search bars
- `aside` — Sidebar ads, related articles

**Why `soup.select_one("article, main, div.entry-content, div[class*='article']")`?**

This CSS selector tries common content containers in order. GFG wraps article content in `div.entry-content` or `div.article-page_flex`. Falling back to `soup.get_text()` (the entire page) is a last resort — it returns more noise but at least doesn't return empty string.

### 4.3 `_fetch_leetcode_text()` — GraphQL

```python
def _fetch_leetcode_text(self, url: str) -> str:
    topic_id = self._leetcode_topic_id(url)
    if topic_id is None:
        return self._fetch_html_text(url)   # fallback

    query = """
    query DiscussTopic($topicId: Int!) {
        topic(id: $topicId) {
            title
            post { content }
        }
    }
    """
    response = requests.post(
        "https://leetcode.com/graphql",
        json={
            "operationName": "DiscussTopic",
            "variables": {"topicId": topic_id},
            "query": query,
        },
        ...
    )
    data = response.json().get("data", {}).get("topic") or {}
    html = "\n".join([data.get("title", ""), data.get("post", {}).get("content", "")])
    return TextCleaner.clean(html)
```

**`_leetcode_topic_id()` — URL parsing:**

```python
def _leetcode_topic_id(self, url: str) -> Optional[int]:
    match = re.search(r"/discuss/(?:[^/]+/)?(\d+)", url)
    return int(match.group(1)) if match else None
```

LeetCode discuss URLs look like:
- `https://leetcode.com/discuss/interview-experience/2345678/Amazon-SDE-Interview`
- `https://leetcode.com/discuss/2345678/`

The regex `(?:[^/]+/)?` is a non-capturing optional group matching any prefix segment (like `interview-experience/`). `(\d+)` captures the numeric topic ID. This ID is the GraphQL primary key.

**Why `or {}` after `get("topic")`?**

If the post was deleted or private, `data.get("topic")` returns `None`. Without the `or {}`, the subsequent `.get("title")` would raise `AttributeError`. The `or {}` substitutes an empty dict, and the subsequent `.get()` calls return empty strings.

**Why pass the HTML content through `TextCleaner.clean()` even for GraphQL?**

LeetCode's `post.content` field contains **HTML** (the post is rendered with an WYSIWYG editor). Raw HTML contains `<p>`, `<code>`, `<ul>` tags that would appear as literal text in the extracted questions. `TextCleaner` strips HTML via BeautifulSoup before further cleaning.

---

## 5. `TextCleaner` — Noise Removal

**File:** `backend/companies/text_cleaner.py`

```python
class TextCleaner:
    MIN_LINE_LENGTH = 15

    NOISE_PATTERNS = [
        r"copyright.*", r"all rights reserved.*", r"privacy policy.*",
        r"terms of service.*", r"cookie policy.*", r"share this.*",
        r"follow us.*", r"subscribe.*", r"advertisement.*",
        r"sign in.*", r"login.*", r"register.*", r"table of contents.*",
    ]

    @classmethod
    def clean(cls, text: str) -> str:
        text = BeautifulSoup(text, "html.parser").get_text("\n")   # strip HTML
        text = re.sub(r"https?://\S+", " ", text)                  # remove URLs
        text = re.sub(r"\S+@\S+", " ", text)                       # remove emails
        text = re.sub(r"```.*?```", " ", text, flags=re.S)         # remove code fences
        text = re.sub(r"[ \t]+", " ", text)                        # collapse spaces
        text = re.sub(r"\n\s*\n+", "\n", text)                     # collapse blank lines

        cleaned = []
        for line in text.splitlines():
            line = line.strip()
            if len(line) < cls.MIN_LINE_LENGTH:
                continue
            lower = line.lower()
            if not any(re.match(p, lower) for p in cls.NOISE_PATTERNS):
                cleaned.append(line)

        return "\n".join(cleaned)
```

### Why each cleaning step:

| Step | Why |
|---|---|
| `BeautifulSoup.get_text("\n")` | Converts `<p>text</p>` → `text\n`. The `\n` separator preserves paragraph structure for line-based filtering |
| Remove URLs | URLs are not questions. They add noise to LLM context and confuse the question extractor |
| Remove emails | Author emails appear in GFG article footers; irrelevant |
| Remove code fences | Code blocks in the raw post aren't questions; they're solutions. Removing them prevents the question extractor from treating code as a question |
| Collapse spaces/newlines | Multiple spaces from HTML formatting (`&nbsp;`) become single spaces |
| `MIN_LINE_LENGTH = 15` | Lines shorter than 15 chars are navigation crumbs, category labels, or single words. "Like", "Share", "GFG" — none of these are questions |
| NOISE_PATTERNS | Footer/header text that survived the HTML stripping. Matched case-insensitively at line start |

**Why `@classmethod`?**

`TextCleaner` has no instance state. Making `clean()` a class method means callers write `TextCleaner.clean(text)` without needing to instantiate the class. It's a utility function packaged in a class for namespace clarity.

---

## 6. `QuestionScraper` — Orchestrator

```python
class QuestionScraper:
    TRUSTED_SOURCES = {
        "leetcode.com": QuestionSource.LEETCODE,
        "geeksforgeeks.org": QuestionSource.GFG,
    }

    def scrape_experiences(
        self,
        company: str = "",
        target_count: int = 5,
        question_type: str = "",
    ) -> list[dict]:
        experiences = []
        seen = set()

        for query in self._queries(company, question_type):
            if len(experiences) >= target_count:
                break
            for result in self.search_client.search(query, num=10)[:MAX_URLS_PER_QUERY]:
                if len(experiences) >= target_count:
                    break
                url = result.get("link", "")
                source = self._source_for_url(url)
                if not source:
                    continue
                text = self.fetcher.fetch_text(url)
                if len(text) < MIN_TEXT_LENGTH:
                    continue
                fingerprint = self._fingerprint(text)
                if fingerprint in seen:
                    continue
                seen.add(fingerprint)
                experiences.append({...})

        return experiences
```

### 6.1 Query Generation — `_queries()`

```python
def _queries(self, company: str, question_type: str) -> list[str]:
    company_part = f'"{company}" ' if company else ""
    type_part = self._type_search_terms(question_type)
    base = f"{company_part}{type_part}".strip()

    return [
        f'{base} "interview experience" site:leetcode.com/discuss',
        f'{base} "online assessment" site:leetcode.com/discuss',
        f'{base} "interview questions" site:geeksforgeeks.org',
        f'{base} "system design interview" site:geeksforgeeks.org',
    ]
```

**Why quoted company name `"Amazon"`?**

Quotes in Google search force exact phrase match. Without quotes, a search for `Amazon interview` might return results mentioning Amazon River or Amazon Prime. `"Amazon"` forces only pages explicitly mentioning the company by name.

**Why four separate queries?**

Different pages use different terminology:
- `"interview experience"` → personal narrative posts (best source — real questions)
- `"online assessment"` → OA-specific posts (HackerRank-style questions)
- `"interview questions"` → curated article lists on GFG
- `"system design interview"` → system design specific (needs its own query since it's less common)

If only one query was used, a company with few LeetCode posts would return 0 results. Multiple queries increase coverage.

**`_type_search_terms()` — type-to-keywords mapping:**

```python
return {
    "DSA_CODING": "coding questions data structures algorithms",
    "OS": "operating system interview questions",
    "DBMS": "dbms database interview questions",
    ...
}.get(question_type, "coding core cs networks dbms system design questions")
```

The default fallback `"coding core cs networks..."` ensures that when `question_type` is empty (fetch all types), the query still targets technical content.

### 6.2 `_source_for_url()` — Trusted Source Filter

```python
def _source_for_url(self, url: str) -> str:
    for domain, source in self.TRUSTED_SOURCES.items():
        if domain in url:
            return source
    return ""   # empty string = untrusted
```

If `_source_for_url` returns `""` (falsy), the orchestrator calls `continue` and skips that URL. This prevents fetching from random sites in search results (Medium articles, personal blogs, YouTube links).

**Why `if domain in url` (substring match)?**

URLs can have subdomains like `discuss.leetcode.com` or `www.geeksforgeeks.org`. A simple `in` check covers all subdomains without needing regex.

### 6.3 Content Fingerprinting — `_fingerprint()`

```python
def _fingerprint(self, text: str) -> str:
    normalized = re.sub(r"\s+", " ", text.lower()).strip()
    return hashlib.md5(normalized.encode()).hexdigest()
```

**Why fingerprint?**

Serper can return the same URL from multiple queries (e.g., a GFG page about Google that appears in both `"Google" "interview experience"` and `"Google" "interview questions"` queries). Without fingerprinting, the same page would be scraped twice, processed twice by the LLM, and duplicate questions would be inserted.

**Why MD5?**

MD5 is fast (microseconds) and produces a 32-char hex string. We don't need cryptographic security — just a fast hash to detect duplicate content. MD5 is fine for this use case.

**Why normalise whitespace before hashing?**

The same page fetched twice might have slightly different whitespace (trailing newlines, inconsistent indentation). Normalising to single spaces ensures the same logical content always produces the same hash.

### 6.4 `MAX_URLS_PER_QUERY = 8` and `MIN_TEXT_LENGTH = 120`

```python
MAX_URLS_PER_QUERY = 8   # only check first 8 results per query
MIN_TEXT_LENGTH = 120    # skip pages with < 120 chars of clean text
```

**Why `MAX_URLS_PER_QUERY = 8`?**

Serper returns up to 10 results. The first 8 are typically the most relevant (Google's ranking). Beyond position 8, results are often tangentially related. Checking all 10 adds 2 extra HTTP fetches with diminishing returns. This also respects the `rate_limit="10/m"` on the task.

**Why `MIN_TEXT_LENGTH = 120`?**

After HTML stripping and cleaning, some pages return nearly empty text (paywalled content, login-required pages, JavaScript-only pages that returned shell HTML). 120 characters is ~2 short sentences — the minimum for a page to contain any useful interview content.

---

## 7. Standalone Script — `serper_scrap.py`

**File:** `scraper/serper_scrap.py`

This was the **original proof-of-concept scraper** before it was integrated into the Django app. It uses Pydantic models and saves to a JSON file.

```python
class ScrapedExperience(BaseModel):
    company: str
    round_type: str        # "OA" or "Interview"
    target_role: str = "Software Engineer"
    batch_year: Optional[int] = None
    source_platform: str
    source_url: str
    raw_text: str
```

**Differences from the production scraper:**

| Feature | `serper_scrap.py` | `companies/scraper.py` |
|---|---|---|
| Output | JSON file (`django_seed_data.json`) | Python list returned to Celery task |
| Round classification | OA vs Interview | Not classified (LLM does type classification) |
| Year extraction | Yes (`extract_year()`) | Not needed (LLM handles metadata) |
| Pydantic validation | Yes | No (plain dicts) |
| Django integration | No | Yes |

### `extract_year()`

```python
def extract_year(text: str) -> Optional[int]:
    match = re.search(r'\b(202[0-9])\b', text)
    if match:
        year = int(match.group(1))
        if 2020 <= year <= current_year + 2:
            return year
    return None
```

**Why `202[0-9]`?** Matches years 2020–2029. The sanity check `<= current_year + 2` prevents matching "2099" if a post mentions a futuristic date.

### `classify_round_type()`

```python
oa_keywords = ["online assessment", " oa ", "-oa-", "hackerrank", "codesignal", "mettl", "aptitude"]
if any(kw in text_lower or kw in url_lower for kw in oa_keywords):
    return "OA"
return "Interview"
```

**Why check the URL too?**

Some LeetCode posts have `"oa"` in the URL path (`/discuss/interview-question/2345-amazon-oa-2024/`) even if the body doesn't use the full phrase "online assessment". Checking both prevents misclassification.

**Why `" oa "` (with spaces) in the keywords list?**

Without spaces, "oa" would match inside words like "load", "board", "road". Space-padding ensures it only matches as a standalone abbreviation.

---

## 8. Constants & Why They Matter

| Constant | Value | File | Rationale |
|---|---|---|---|
| `SERPER_URL` | `https://google.serper.dev/search` | `scraper.py` | Serper's POST endpoint |
| `PAGE_FETCH_SLEEP` | `1.5s` | `scraper.py` | Politeness delay between page fetches to avoid 429s |
| `MIN_TEXT_LENGTH` | `120` chars | `scraper.py` | Filter out paywalled/empty pages |
| `MAX_URLS_PER_QUERY` | `8` | `scraper.py` | Top 8 Google results are the most relevant; beyond that: diminishing returns |
| `MIN_LINE_LENGTH` | `15` chars | `text_cleaner.py` | Short lines are navigation/metadata, not content |
| `User-Agent` | Chrome 125 string | `scraper.py` | Prevent 403s from sites that block non-browser requests |
| `timeout` (Serper) | `10s` | `scraper.py` | API call should be fast; 10s = generous |
| `timeout` (pages) | `15s` | `scraper.py` | Full HTML pages can be slow; 15s = realistic |

---

## 9. Full Data Flow

```
Celery Task: scrape_and_ingest_questions(company="Amazon", question_type="DSA_CODING")
        ↓
QuestionScraper.scrape_experiences("Amazon", target_count=10, question_type="DSA_CODING")
        ↓
_queries("Amazon", "DSA_CODING") →
    [
      '"Amazon" coding questions... "interview experience" site:leetcode.com/discuss',
      '"Amazon" coding questions... "online assessment" site:leetcode.com/discuss',
      '"Amazon" coding questions... "interview questions" site:geeksforgeeks.org',
      '"Amazon" coding questions... "system design interview" site:geeksforgeeks.org',
    ]
        ↓
SearchClient.search(query, num=10) → [{link, title, snippet}, ...]
        ↓
For each result URL (max 8 per query):
    _source_for_url(url) → "LC" or "GFG" or "" (skip if "")
        ↓
    PageFetcher.fetch_text(url)
        → if leetcode.com: _fetch_leetcode_text() [GraphQL]
        → else:            _fetch_html_text()     [BeautifulSoup]
        ↓
    TextCleaner.clean(raw_html_text)
        → strip HTML tags
        → remove URLs, emails, code fences
        → collapse whitespace
        → filter short lines and noise patterns
        ↓
    if len(clean_text) < 120: skip
    if _fingerprint(text) in seen: skip (duplicate page)
        ↓
    experiences.append({text, source_url, source, company})
        ↓
    if len(experiences) >= target_count: break

Return experiences → Celery task continues with LLM extraction
```

---

## 10. Error Handling Strategy

The scraper is designed for **graceful degradation**:

| Failure | Response |
|---|---|
| Serper API down | `search()` returns `[]`, orchestrator moves to next query |
| Page returns 404/403 | `requests.RequestException` caught, `fetch_text()` returns `""` |
| Page text too short | Filtered by `MIN_TEXT_LENGTH` check |
| LeetCode GraphQL fails | Falls back to `_fetch_html_text()` (may return empty for SPA) |
| Same page seen twice | MD5 fingerprint check skips it |
| Celery task itself fails | `max_retries=3`, `default_retry_delay=120` — retried 3 times |

**Why not raise exceptions at the scraper level?**

If one URL fails, the task should continue with the remaining URLs. Only if scraping produces **zero results** and the task completely fails should it retry. The `except Exception as exc: raise self.retry(exc=exc)` in the Celery task wraps the entire scrape operation.
