"""
Scraper Service — Serper API + BeautifulSoup 4 + LeetCode GraphQL
================================================
Architecture:
  1. SerperClient    — Searches Google specifically for full Interview/OA experiences.
  2. PageScraper     — Fetches and parses individual LC (GraphQL) / GFG posts.
  3. QuestionScraper — Orchestrates the download of full experience texts.

DEDUPLICATION STRATEGY:
  --- CHANGE (WHAT): Removed Jaccard Similarity. Now uses MD5 fingerprinting only. ---
  --- CHANGE (WHY): Jaccard is lexical and fails on paraphrased questions. We now 
  rely entirely on the local Hugging Face Semantic Embeddings downstream in tasks.py.
  --- CHANGE (WHAT): Updated to match new LLM service that extracts multiple questions 
  per post and auto-classifies topics. ---
  --- CHANGE (WHY): The scraper now returns raw experience posts as-is. The LLM service 
  handles question extraction, formatting, and topic classification in one shot. ---
"""

import re
import time
import logging
import hashlib
from typing import Optional

import requests
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
from django.conf import settings

logger = logging.getLogger(__name__)

# ─── Constants ────────────────────────────────────────────────────────────────

SERPER_URL = "https://google.serper.dev/search"

# Polite crawling delay
PAGE_FETCH_SLEEP = 2.0  # seconds

# Minimum length for a post to be considered a valid experience
MIN_POST_LENGTH = 150

# Maximum URLs to fetch per query
MAX_URLS_PER_QUERY = 8


# ─── Serper API Client ────────────────────────────────────────────────────────

class SerperClient:
    """
    Thin wrapper around the Serper.dev Google Search API.
    """
    def __init__(self):
        self.api_key = settings.SERPER_API_KEY
        if not self.api_key:
            raise ValueError("SERPER_API_KEY is not set in environment.")

    def search(self, query: str, num: int = 10) -> list[dict]:
        """
        Execute a search query against Serper API.
        
        Args:
            query: Search query string
            num: Number of results to request
            
        Returns:
            List of organic search result dictionaries
        """
        try:
            response = requests.post(
                SERPER_URL,
                headers={"X-API-KEY": self.api_key, "Content-Type": "application/json"},
                json={"q": query, "num": num},
                timeout=10,
            )
            response.raise_for_status()
            results = response.json().get("organic", [])
            logger.info("Serper: '%s' → %d results", query, len(results))
            return results
        except requests.RequestException as exc:
            logger.error("Serper search failed for '%s': %s", query, exc)
            return []

    # --- CHANGE (WHAT): Replaced build_queries with build_experience_queries. ---
    # --- CHANGE (WHY): Instead of searching for generic topics (like "Binary Trees"), 
    # we now strictly hunt for raw candidate stories. We use the broadened /discuss Dork 
    # to catch LeetCode's new forum URL structures. ---
    def build_experience_queries(self, company: str) -> list[str]:
        """
        Builds Google search queries strictly targeting Interview and OA experiences.
        We bypass topics entirely and let the LLM extract the topics later.
        
        Args:
            company: Target company name for context
            
        Returns:
            List of search query strings
        """
        company_ctx = f'"{company}" ' if company else ""
        
        return [
            f'{company_ctx} "Interview Experience" site:leetcode.com/discuss',
            f'{company_ctx} "Online Assessment" site:leetcode.com/discuss',
            f'{company_ctx} "Interview Experience" site:geeksforgeeks.org',
        ]


# ─── Page Scraper ─────────────────────────────────────────────────────────────

class PageScraper:
    """
    Fetches a URL and extracts the main text body.
    Handles both LeetCode (via GraphQL) and GeeksForGeeks (via HTML parsing).
    """
    def __init__(self):
        self.ua = UserAgent()

    def _get_html(self, url: str) -> Optional[str]:
        """
        Fetch HTML content from a URL with polite delays.
        
        Args:
            url: Target URL to fetch
            
        Returns:
            HTML string or None if fetch fails
        """
        try:
            headers = {
                "User-Agent": self.ua.random,
                "Accept-Language": "en-US,en;q=0.9",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            }
            resp = requests.get(url, headers=headers, timeout=15)
            resp.raise_for_status()
            time.sleep(PAGE_FETCH_SLEEP)
            return resp.text
        except requests.RequestException as exc:
            logger.warning("Failed to fetch %s: %s", url, exc)
            return None

    def _extract_leetcode(self, url: str) -> list[str]:
        """
        Uses LeetCode GraphQL to fetch the raw post content cleanly.
        This avoids all the HTML noise and JavaScript rendering issues.
        
        Args:
            url: LeetCode discuss post URL
            
        Returns:
            List containing the post text (or empty list if extraction fails)
        """
        try:
            headers = {"User-Agent": self.ua.random, "Content-Type": "application/json"}
            content = ""

            # Target standard discuss posts (which is where experiences are posted)
            match_discuss = re.search(r'/discuss/(?:[^/]+)/(\d+)', url)
            if match_discuss:
                topic_id = int(match_discuss.group(1))
                query = """
                query DiscussTopic($topicId: Int!) { 
                    topic(id: $topicId) { 
                        post { 
                            content 
                        } 
                    } 
                }
                """
                resp = requests.post(
                    'https://leetcode.com/graphql', 
                    json={
                        "operationName": "DiscussTopic", 
                        "variables": {"topicId": topic_id}, 
                        "query": query
                    }, 
                    headers=headers, 
                    timeout=10
                )
                resp.raise_for_status()
                content = resp.json().get('data', {}).get('topic', {}).get('post', {}).get('content', '')

            if content and len(content) > MIN_POST_LENGTH:
                # Strip HTML tags returned by GraphQL so the LLM gets clean text
                clean_text = BeautifulSoup(content, "html.parser").get_text(separator="\n", strip=True)
                return [clean_text]
                
            return []
        except Exception as e:
            logger.warning(f"LeetCode GraphQL failed for {url}: {e}")
            return []

    def _extract_gfg(self, soup: BeautifulSoup) -> list[str]:
        """
        Extracts the main article body from GeeksForGeeks experience posts.
        
        Args:
            soup: BeautifulSoup object of the parsed page
            
        Returns:
            List containing the article text (or empty list if extraction fails)
        """
        content = soup.select_one("div.entry-content, article, div[class*='article']")
        if content:
            text = content.get_text(separator="\n", strip=True)
            if len(text) > MIN_POST_LENGTH:
                return [text]
        return []

    def scrape(self, url: str) -> list[str]:
        """
        Main scraping entry point. Routes to appropriate extractor based on URL.
        
        Args:
            url: Target URL to scrape
            
        Returns:
            List of extracted text content (usually single element)
        """
        # LeetCode gets special treatment via GraphQL
        if "leetcode.com" in url:
            return self._extract_leetcode(url)

        # For other sites (GFG), use traditional HTML scraping
        html = self._get_html(url)
        if not html:
            return []

        soup = BeautifulSoup(html, "html.parser")
        
        # Remove noise elements before extraction
        for tag in soup(["script", "style", "nav", "footer", "header", "aside", "form", ".advertisement"]):
            tag.decompose()

        return self._extract_gfg(soup)


def text_fingerprint(text: str) -> str:
    """
    Generate MD5 hash of normalized text for exact deduplication.
    
    --- CHANGE (WHAT): This replaces Jaccard similarity for initial dedup. ---
    --- CHANGE (WHY): MD5 is faster and catches exact duplicates. Semantic 
    deduplication happens later with embeddings. ---
    
    Args:
        text: Raw text to fingerprint
        
    Returns:
        MD5 hash string
    """
    normalized = re.sub(r'\s+', ' ', text.lower().strip())
    return hashlib.md5(normalized.encode()).hexdigest()


# ─── Orchestrator ─────────────────────────────────────────────────────────────

class QuestionScraper:
    """
    Orchestrates the full scraping pipeline:
    1. Search for interview experiences
    2. Fetch and parse each result
    3. Deduplicate by MD5 fingerprint
    4. Return cleaned experience texts
    """
    
    TRUSTED_DOMAINS = ["leetcode.com", "geeksforgeeks.org"]

    def __init__(self):
        self.serper = SerperClient()
        self.scraper = PageScraper()

    # --- CHANGE (WHAT): Renamed and simplified to scrape_experiences. ---
    # --- CHANGE (WHY): We no longer care about mapping topics during the scrape. We 
    # just want to download the raw posts and hand them to the LLM. ---
    def scrape_experiences(self, company: str, target_count: int = 5) -> list[dict]:
        """
        Downloads full interview experience posts to feed into the LLM.
        
        --- CHANGE (WHAT): Added company field to return dict. ---
        --- CHANGE (WHY): The new LLM service expects company context for better 
        question extraction and topic classification. ---
        
        Args:
            company: Target company for search queries
            target_count: Approximate number of unique experiences to return
            
        Returns:
            List of dicts with keys: text, source_url, source, company
        """
        queries = self.serper.build_experience_queries(company)
        all_experiences = []
        seen_fps = set()

        for query in queries:
            if len(all_experiences) >= target_count:
                break
            
            results = self.serper.search(query, num=10)
            urls = [
                r.get("link") 
                for r in results 
                if any(d in r.get("link", "") for d in self.TRUSTED_DOMAINS)
            ][:MAX_URLS_PER_QUERY]

            for url in urls:
                if len(all_experiences) >= target_count:
                    break
                    
                texts = self.scraper.scrape(url)
                for text in texts:
                    fp = text_fingerprint(text)
                    if fp not in seen_fps:
                        seen_fps.add(fp)
                        source = "LC" if "leetcode" in url else "GFG"
                        
                        # --- CHANGE (WHAT): Added company to return dict. ---
                        # --- CHANGE (WHY): LLM service uses company context for 
                        # better question extraction and topic classification. ---
                        all_experiences.append({
                            "text": text, 
                            "source_url": url, 
                            "source": source,
                            "company": company  # Pass company context downstream
                        })
                    
        logger.info("Scraped %d full interview experiences for %s", len(all_experiences), company)
        return all_experiences