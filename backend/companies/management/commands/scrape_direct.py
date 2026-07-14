import os
import json
import requests
import re
import hashlib
from datetime import datetime
from bs4 import BeautifulSoup
from django.core.management.base import BaseCommand
from companies.models import Company, PlacementExperience
from companies.scraper import QuestionScraper
from django.conf import settings

class Command(BaseCommand):
    help = 'Scrapes GFG/LeetCode and saves directly to the Django database, checking for duplicates.'

    def handle(self, *args, **kwargs):
        SERPER_API_KEY = os.environ.get('SERPER_API_KEY') or getattr(settings, 'SERPER_API_KEY', None)
        if not SERPER_API_KEY:
            self.stdout.write(self.style.ERROR("[-] ERROR: SERPER_API_KEY is missing!"))
            return

        HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        companies_to_scrape = ["Sprinklr", "Unify Apps", "Tekion", "Headout", "Oracle"]

        self.stdout.write(self.style.NOTICE("[*] Booting Direct-to-DB Scraper Pipeline..."))

        for company_name in companies_to_scrape:
            # Get or create the company in DB instantly
            company_obj, _ = Company.objects.get_or_create(name=company_name)
            
            for round_target in ["OA", "Interview"]:
                self.stdout.write(f"\n[*] Searching Google for: {company_name} {round_target}s...")
                
                # 1. Get URLs from Serper
                if round_target == "OA":
                    query = (
                        f'"{company_name}" ("online assessment" OR "OA" OR "hackerrank") '
                        '(site:leetcode.com/discuss OR site:geeksforgeeks.org)'
                    )
                else:
                    query = (
                        f'"{company_name}" ("interview experience" OR "technical interview") '
                        '(site:leetcode.com/discuss OR site:geeksforgeeks.org)'
                    )
                response = requests.post("https://google.serper.dev/search", headers={'X-API-KEY': SERPER_API_KEY, 'Content-Type': 'application/json'}, json={"q": query, "num": 5})
                urls = [item['link'] for item in response.json().get('organic', [])]

                for url in urls:
                    # 2. FAST DB DEDUPLICATION: Check if URL already exists
                    if PlacementExperience.objects.filter(source_url=url).exists():
                        self.stdout.write(self.style.WARNING(f"  [~] Skipped: URL already in DB -> {url}"))
                        continue

                    # 3. Scrape the content
                    raw_text = None
                    platform = "Unknown"
                    if "geeksforgeeks.org" in url:
                        raw_text = self.scrape_gfg(url, HEADERS)
                        platform = "GeeksforGeeks"
                    elif "leetcode.com" in url:
                        raw_text = self.scrape_leetcode(url, HEADERS)
                        platform = "LeetCode"

                    if not raw_text:
                        continue
                    if not QuestionScraper._matches_company(raw_text, company_name):
                        self.stdout.write(
                            self.style.WARNING(
                                f"  [~] Skipped: content is not for {company_name} -> {url}"
                            )
                        )
                        continue

                    # 4. HASH CHECK: Prevent exact duplicate content from different URLs
                    content_hash = hashlib.sha256(raw_text.encode('utf-8')).hexdigest()
                    
                    if PlacementExperience.objects.filter(content_hash=content_hash).exists():
                        continue

                    # 5. Determine specifics
                    db_round_type = 'OA' if self.classify_round_type(raw_text, url) == 'OA' else 'INTERVIEW'
                    batch_year = self.extract_year(raw_text)

                    # 6. SAVE DIRECTLY TO DB
                    PlacementExperience.objects.create(
                        company=company_obj,
                        round_type=db_round_type,
                        target_role="Software Engineer",
                        batch_year=batch_year,
                        source_platform=platform,
                        source_url=url,
                        raw_text=raw_text
                    )
                    self.stdout.write(self.style.SUCCESS(f"  [+] Saved New Record: {company_name} {db_round_type}"))

        self.stdout.write(self.style.SUCCESS("\n[✓] Scraping & Database Seeding Complete!"))

    def extract_year(self, text):
        match = re.search(r'\b(202[0-9])\b', text)
        return int(match.group(1)) if match and 2020 <= int(match.group(1)) <= datetime.now().year + 2 else None

    def classify_round_type(self, text, url):
        return "OA" if any(kw in text.lower() or kw in url.lower() for kw in ["online assessment", " oa ", "-oa-", "hackerrank", "codesignal", "mettl", "aptitude"]) else "Interview"

    def scrape_gfg(self, url, headers):
        try:
            resp = requests.get(url, headers=headers, timeout=10)
            soup = BeautifulSoup(resp.text, 'html.parser')
            div = soup.find('div', class_='text') or soup.find('div', class_='article-page_flex')
            return div.get_text(separator='\n', strip=True) if div else None
        except: return None

    def scrape_leetcode(self, url, headers):
        try:
            topic_id = re.search(r'/discuss/(?:interview-experience|compensation|interview-question)/(\d+)/', url).group(1)
            resp = requests.post('https://leetcode.com/graphql', json={"operationName": "DiscussTopic", "variables": {"topicId": int(topic_id)}, "query": "query DiscussTopic($topicId: Int!) { topic(id: $topicId) { post { content } } }"}, headers=headers, timeout=10)
            return resp.json()['data']['topic']['post']['content']
        except: return None
