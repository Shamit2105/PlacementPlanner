import hashlib
import logging
import re
import time
from typing import Optional
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from django.conf import settings

from .models import QuestionSource
from .text_cleaner import TextCleaner

logger = logging.getLogger(__name__)

SERPER_URL = "https://google.serper.dev/search"
PAGE_FETCH_SLEEP = 1.5
MIN_TEXT_LENGTH = 120
MAX_URLS_PER_QUERY = 5   # searched results to inspect per query
MAX_PAGES_TOTAL = 5      # hard cap on pages actually fetched per scrape_experiences call


class SearchClient:
    def __init__(self):
        self.api_key = settings.SERPER_API_KEY
        if not self.api_key:
            raise ValueError("SERPER_API_KEY is not set.")

    def search(self, query: str, num: int = 10) -> list[dict]:
        try:
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
        except requests.RequestException as exc:
            logger.warning("Search failed for %r: %s", query, exc)
            return []


class PageFetcher:
    USER_AGENT = (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/125.0 Safari/537.36"
    )

    def fetch_text(self, url: str) -> str:
        hostname = (urlparse(url).hostname or "").lower()
        if hostname == "leetcode.com" or hostname.endswith(".leetcode.com"):
            return self._fetch_leetcode_text(url)
        return self._fetch_html_text(url)

    def _fetch_html_text(self, url: str) -> str:
        try:
            response = requests.get(
                url,
                headers={"User-Agent": self.USER_AGENT},
                timeout=15,
            )
            response.raise_for_status()
            time.sleep(PAGE_FETCH_SLEEP)
        except requests.RequestException as exc:
            logger.warning("Fetch failed for %s: %s", url, exc)
            return ""

        soup = BeautifulSoup(response.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()

        article = soup.select_one(
            "article, main, div.entry-content, div[class*='article'], "
            "div[class*='content'], div[class*='post-body'], div.post"
        )
        text = (
            article.get_text("\n", strip=True)
            if article
            else soup.get_text("\n", strip=True)
        )
        return TextCleaner.clean(text)

    def _fetch_leetcode_text(self, url: str) -> str:
        """
        Try LeetCode GraphQL first (works when topic ID is numeric and the
        endpoint is reachable). Fall back to plain HTML scraping if GraphQL
        returns no content — the HTML path still yields enough text for LLM
        extraction even though it requires no authentication token.
        """
        topic_id = self._leetcode_topic_id(url)
        if topic_id is not None:
            text = self._leetcode_graphql(url, topic_id)
            if text:
                return text
            logger.info(
                "LeetCode GraphQL returned no content for %s — falling back to HTML", url
            )

        # HTML fallback: LeetCode discuss pages render server-side content that
        # is accessible without a login token.
        return self._fetch_leetcode_html(url)

    def _leetcode_graphql(self, url: str, topic_id: int) -> str:
        """Return cleaned post content via GraphQL, or '' on any failure."""
        # LeetCode's GraphQL endpoint needs a CSRF token that we obtain from a
        # lightweight HEAD request to the discuss page first.
        csrf_token = self._fetch_leetcode_csrf(url)

        query = """
        query DiscussTopic($topicId: Int!) {
            topic(id: $topicId) {
                title
                post { content }
            }
        }
        """

        headers = {
            "User-Agent": self.USER_AGENT,
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Referer": url,
            "Origin": "https://leetcode.com",
        }
        if csrf_token:
            headers["x-csrftoken"] = csrf_token

        try:
            response = requests.post(
                "https://leetcode.com/graphql",
                json={
                    "operationName": "DiscussTopic",
                    "variables": {"topicId": topic_id},
                    "query": query,
                },
                headers=headers,
                timeout=12,
            )
            response.raise_for_status()
            payload = response.json()
            errors = payload.get("errors", [])
            data = payload.get("data", {}).get("topic") or {}
            content = data.get("post", {}).get("content", "")
            if errors or not content:
                logger.warning(
                    "LeetCode GraphQL returned no post content for %s: %s",
                    url,
                    errors or "empty topic/post",
                )
                return ""
            html = "\n".join([data.get("title", ""), content])
            return TextCleaner.clean(html)
        except (requests.RequestException, ValueError) as exc:
            logger.warning("LeetCode GraphQL failed for %s: %s", url, exc)
            return ""

    def _fetch_leetcode_csrf(self, url: str) -> str:
        """Grab csrftoken cookie from LeetCode so GraphQL accepts the request."""
        try:
            resp = requests.get(
                url,
                headers={"User-Agent": self.USER_AGENT},
                timeout=10,
                allow_redirects=True,
            )
            return resp.cookies.get("csrftoken", "")
        except requests.RequestException:
            return ""

    def _fetch_leetcode_html(self, url: str) -> str:
        """
        Scrape a LeetCode discuss page directly.
        The page renders a JSON payload in a <script id="__NEXT_DATA__"> tag;
        we extract the post body from there before falling back to visible text.
        """
        try:
            response = requests.get(
                url,
                headers={"User-Agent": self.USER_AGENT},
                timeout=15,
            )
            response.raise_for_status()
            time.sleep(PAGE_FETCH_SLEEP)
        except requests.RequestException as exc:
            logger.warning("LeetCode HTML fetch failed for %s: %s", url, exc)
            return ""

        soup = BeautifulSoup(response.text, "html.parser")

        # 1. Try the Next.js JSON payload — richest source of content.
        next_data = soup.find("script", {"id": "__NEXT_DATA__"})
        if next_data and next_data.string:
            import json as _json
            try:
                nd = _json.loads(next_data.string)
                # Path varies; do a deep search for "content" key with HTML.
                content = self._deep_find(nd, "content")
                if content and len(content) > MIN_TEXT_LENGTH:
                    return TextCleaner.clean(content)
            except (ValueError, TypeError):
                pass

        # 2. Fall back to rendered visible text.
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()

        # LeetCode discuss posts live inside [class*="discuss-markdown"] or similar.
        post_div = soup.select_one(
            "div[class*='discuss-markdown'], div[class*='post-content'], "
            "div[data-key='description-content'], div[class*='content__']"
        )
        text = (
            post_div.get_text("\n", strip=True)
            if post_div
            else soup.get_text("\n", strip=True)
        )
        return TextCleaner.clean(text)

    @staticmethod
    def _deep_find(obj, key: str):
        """Recursively search a nested dict/list for the first occurrence of *key*."""
        if isinstance(obj, dict):
            if key in obj and isinstance(obj[key], str):
                return obj[key]
            for v in obj.values():
                result = PageFetcher._deep_find(v, key)
                if result:
                    return result
        elif isinstance(obj, list):
            for item in obj:
                result = PageFetcher._deep_find(item, key)
                if result:
                    return result
        return None

    def _leetcode_topic_id(self, url: str) -> Optional[int]:
        match = re.search(r"/discuss/(?:[^/]+/)?(\d+)", url)
        return int(match.group(1)) if match else None


class QuestionScraper:
    TRUSTED_SOURCES = {
        "leetcode.com": QuestionSource.LEETCODE,
        "geeksforgeeks.org": QuestionSource.GFG,
    }

    def __init__(self):
        self.search_client = SearchClient()
        self.fetcher = PageFetcher()

    def scrape_experiences(
        self,
        company: str = "",
        target_count: int = 5,
        question_type: str = "",
    ) -> list[dict]:
        """
        Fetch up to *target_count* interview-experience pages from trusted
        sources.  Enforces a hard cap of MAX_PAGES_TOTAL pages fetched across
        ALL queries so a single API call never downloads unbounded content.
        """
        experiences = []
        seen = set()
        pages_fetched = 0                        # ← global page counter

        for query in self._queries(company, question_type):
            if len(experiences) >= target_count:
                break
            if pages_fetched >= MAX_PAGES_TOTAL:  # ← hard cap enforced here
                break

            for result in self.search_client.search(query, num=10)[:MAX_URLS_PER_QUERY]:
                if len(experiences) >= target_count:
                    break
                if pages_fetched >= MAX_PAGES_TOTAL:  # ← also inside inner loop
                    break

                url = result.get("link", "")
                source = self._source_for_url(url)
                if not source:
                    continue

                # For GFG, only accept actual interview-experience articles,
                # not question-list / topic-overview pages.
                if source == QuestionSource.GFG and not self._is_gfg_interview_experience(url):
                    logger.info("Skipping GFG non-experience URL: %s", url)
                    continue

                pages_fetched += 1               # count before fetch
                text = self.fetcher.fetch_text(url)
                if len(text) < MIN_TEXT_LENGTH:
                    continue
                if company and not self._matches_company(text, company):
                    logger.info(
                        "Skipping %s: page content does not identify requested company %r",
                        url,
                        company,
                    )
                    continue

                fingerprint = self._fingerprint(text)
                if fingerprint in seen:
                    continue

                seen.add(fingerprint)
                experiences.append(
                    {
                        "text": text,
                        "source_url": url,
                        "source": source,
                        "company": company,
                    }
                )

        logger.info(
            "scrape_experiences: fetched %d pages → %d valid experiences (cap=%d)",
            pages_fetched,
            len(experiences),
            MAX_PAGES_TOTAL,
        )
        return experiences

    # ── Query generation ──────────────────────────────────────────────────────

    def _queries(self, company: str, question_type: str) -> list[str]:
        company_part = f'"{company}" ' if company else ""
        type_part = self._type_search_terms(question_type)

        base = f"{company_part}{type_part}".strip()
        if not base:
            base = "technical interview"

        return [
            # LeetCode discuss — interview experiences ONLY
            f'{company_part}"interview experience" {type_part} site:leetcode.com/discuss',
            f'{company_part}"online assessment" {type_part} site:leetcode.com/discuss',
            # GFG — restrict to the interview-experiences section
            f'{company_part}interview experience {type_part} site:geeksforgeeks.org/interview-experiences',
            f'{company_part}interview experience {type_part} site:geeksforgeeks.org/experiences',
        ]

    def _type_search_terms(self, question_type: str) -> str:
        return {
            "DSA_CODING": "coding data structures algorithms",
            "DSA_THEORY": "data structures algorithms theory",
            "OS": "operating system",
            "DBMS": "database dbms",
            "NETWORKS": "computer networks",
            "SYSTEM_DESIGN": "system design",
        }.get(question_type, "")

    # ── URL validation ────────────────────────────────────────────────────────

    def _source_for_url(self, url: str) -> str:
        parsed = urlparse(url)
        hostname = (parsed.hostname or "").lower()

        for domain, source in self.TRUSTED_SOURCES.items():
            if hostname == domain or hostname.endswith(f".{domain}"):
                # LeetCode: only /discuss/ paths contain interview experiences.
                if domain == "leetcode.com" and not parsed.path.startswith("/discuss/"):
                    return ""
                return source
        return ""

    @staticmethod
    def _is_gfg_interview_experience(url: str) -> bool:
        """
        Return True only for GFG pages that live under the interview-experience
        or experiences subpath — not generic question-list or practice pages.
        """
        path = urlparse(url).path.lower().rstrip("/")
        # Accept /interview-experiences/... and /experiences/...
        # Reject list pages like /interview-experiences/ (no article slug)
        # and practice/topic pages.
        if re.match(r"/(interview-experiences|experiences)/[a-z0-9]", path):
            return True
        return False

    @staticmethod
    def _matches_company(text: str, company: str) -> bool:
        """Return True only when the scraped page explicitly names *company*."""
        words = re.findall(r"[\w]+", company, flags=re.UNICODE)
        if not words:
            return True
        pattern = r"(?<!\w)" + r"[\s._-]+".join(map(re.escape, words)) + r"(?!\w)"
        return re.search(pattern, text, flags=re.IGNORECASE) is not None

    def _fingerprint(self, text: str) -> str:
        normalized = re.sub(r"\s+", " ", text.lower()).strip()
        return hashlib.md5(normalized.encode()).hexdigest()
