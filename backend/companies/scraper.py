import hashlib
import logging
import re
import time
from typing import Optional

import requests
from bs4 import BeautifulSoup
from django.conf import settings

from .models import QuestionSource
from .text_cleaner import TextCleaner

logger = logging.getLogger(__name__)

SERPER_URL = "https://google.serper.dev/search"
PAGE_FETCH_SLEEP = 1.5
MIN_TEXT_LENGTH = 120
MAX_URLS_PER_QUERY = 8


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
        if "leetcode.com" in url:
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

        article = soup.select_one("article, main, div.entry-content, div[class*='article']")
        text = article.get_text("\n", strip=True) if article else soup.get_text("\n", strip=True)
        return TextCleaner.clean(text)

    def _fetch_leetcode_text(self, url: str) -> str:
        topic_id = self._leetcode_topic_id(url)
        if topic_id is None:
            return self._fetch_html_text(url)

        query = """
        query DiscussTopic($topicId: Int!) {
            topic(id: $topicId) {
                title
                post { content }
            }
        }
        """

        try:
            response = requests.post(
                "https://leetcode.com/graphql",
                json={
                    "operationName": "DiscussTopic",
                    "variables": {"topicId": topic_id},
                    "query": query,
                },
                headers={
                    "User-Agent": self.USER_AGENT,
                    "Content-Type": "application/json",
                },
                timeout=10,
            )
            response.raise_for_status()
            data = response.json().get("data", {}).get("topic") or {}
        except requests.RequestException as exc:
            logger.warning("LeetCode GraphQL failed for %s: %s", url, exc)
            return ""

        html = "\n".join([data.get("title", ""), data.get("post", {}).get("content", "")])
        return TextCleaner.clean(html)

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
                experiences.append(
                    {
                        "text": text,
                        "source_url": url,
                        "source": source,
                        "company": company,
                    }
                )

        return experiences

    def _queries(self, company: str, question_type: str) -> list[str]:
        company_part = f'"{company}" ' if company else ""
        type_part = self._type_search_terms(question_type)

        base = f"{company_part}{type_part}".strip()
        if not base:
            base = "technical interview questions"

        return [
            f'{base} "interview experience" site:leetcode.com/discuss',
            f'{base} "online assessment" site:leetcode.com/discuss',
            f'{base} "interview questions" site:geeksforgeeks.org',
            f'{base} "system design interview" site:geeksforgeeks.org',
        ]

    def _type_search_terms(self, question_type: str) -> str:
        return {
            "DSA_CODING": "coding questions data structures algorithms",
            "DSA_THEORY": "core cs data structures algorithms theory",
            "OS": "operating system interview questions",
            "DBMS": "dbms database interview questions",
            "NETWORKS": "computer networks interview questions",
            "SYSTEM_DESIGN": "system design interview questions",
        }.get(question_type, "coding core cs networks dbms system design questions")

    def _source_for_url(self, url: str) -> str:
        for domain, source in self.TRUSTED_SOURCES.items():
            if domain in url:
                return source
        return ""

    def _fingerprint(self, text: str) -> str:
        normalized = re.sub(r"\s+", " ", text.lower()).strip()
        return hashlib.md5(normalized.encode()).hexdigest()
