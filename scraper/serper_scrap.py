import os
import json
import requests
import re
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from pydantic import BaseModel
from typing import Optional
import datetime

load_dotenv()
SERPER_API_KEY = os.getenv('SERPER_API_KEY')

class ScrapedExperience(BaseModel):
    company: str
    round_type: str  # "OA" or "Interview"
    target_role: str = "Software Engineer"
    batch_year: Optional[int] = None
    source_platform: str
    source_url: str
    raw_text: str

scraped_database = []

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

def extract_year(text: str) -> Optional[int]:
    """Tries to find the graduation batch year in the text (e.g., 2024, 2025)."""
    current_year = datetime.datetime.now().year
    # Look for years between 2020 and current_year + 2
    match = re.search(r'\b(202[0-9])\b', text)
    if match:
        year = int(match.group(1))
        # Sanity check
        if 2020 <= year <= current_year + 2:
            return year
    return None

def classify_round_type(text: str, url: str, expected_type: str) -> str:
    """Double checks if the content is an OA or Interview based on keywords."""
    text_lower = text.lower()
    url_lower = url.lower()
    
    oa_keywords = ["online assessment", " oa ", "-oa-", "hackerrank", "codesignal", "mettl", "aptitude"]
    
    # If the URL or text heavily implies an OA, tag it as OA regardless of the search intent
    if any(kw in text_lower or kw in url_lower for kw in oa_keywords):
        return "OA"
    return "Interview"

def scrape_gfg(url, company, expected_type) -> Optional[ScrapedExperience]:
    print(f"  [+] Scraping GFG: {url}")
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        if response.status_code != 200: return None

        soup = BeautifulSoup(response.text, 'html.parser')
        content_div = soup.find('div', class_='text') or soup.find('div', class_='article-page_flex')
        if not content_div: return None
            
        raw_text = content_div.get_text(separator='\n', strip=True)
        
        return ScrapedExperience(
            company=company,
            round_type=classify_round_type(raw_text, url, expected_type),
            batch_year=extract_year(raw_text),
            source_platform="GeeksforGeeks",
            source_url=url,
            raw_text=raw_text
        )
    except Exception as e:
        print(f"  [-] GFG Failed: {e}")
        return None

def scrape_leetcode(url: str, company: str, expected_type: str) -> Optional[ScrapedExperience]:
    print(f"  [+] Scraping LeetCode: {url}")
    try:
        match = re.search(r'/discuss/(?:interview-experience|compensation|interview-question)/(\d+)/', url)
        if not match: return None
            
        topic_id = match.group(1)
        graphql_query = {
            "operationName": "DiscussTopic",
            "variables": {"topicId": int(topic_id)},
            "query": "query DiscussTopic($topicId: Int!) { topic(id: $topicId) { post { content } } }"
        }

        response = requests.post('https://leetcode.com/graphql', json=graphql_query, headers=HEADERS, timeout=10)
        raw_text = response.json()['data']['topic']['post']['content']

        return ScrapedExperience(
            company=company,
            round_type=classify_round_type(raw_text, url, expected_type),
            batch_year=extract_year(raw_text),
            source_platform="LeetCode",
            source_url=url,
            raw_text=raw_text
        )
    except Exception as e:
        print(f"  [-] LeetCode Failed: {e}")
        return None

def get_targeted_urls(company: str, target_type: str) -> list:
    """Searches specifically for OA or Interview experiences."""
    print(f"\n[*] Searching Google for: {company} {target_type}s...")
    
    if target_type == "OA":
        query = f'"{company}" AND ("online assessment" OR "OA" OR "hackerrank") site:leetcode.com OR site:geeksforgeeks.org'
    else:
        query = f'"{company}" AND ("interview experience" OR "technical interview") site:leetcode.com OR site:geeksforgeeks.org'
    
    url = "https://google.serper.dev/search"
    payload = json.dumps({"q": query, "num": 5}) 
    headers = {'X-API-KEY': SERPER_API_KEY, 'Content-Type': 'application/json'}

    response = requests.post(url, headers=headers, data=payload)
    results = response.json()
    
    return [item['link'] for item in results.get('organic', [])]

def run_pipeline(target_companies: list):
    for company in target_companies:
        for round_target in ["OA", "Interview"]:
            urls = get_targeted_urls(company, round_target)
            
            for url in urls:
                experience = None
                if "geeksforgeeks.org" in url:
                    experience = scrape_gfg(url, company, round_target)
                elif "leetcode.com" in url:
                    experience = scrape_leetcode(url, company, round_target)
                    
                if experience:
                    scraped_database.append(experience)
                    print(f"Saved as {experience.round_type} (Batch: {experience.batch_year or 'Unknown'})")


if __name__ == "__main__":
    if not SERPER_API_KEY:
        print("ERROR: Missing SERPER_API_KEY in .env file.")
        exit()

    companies_to_scrape = ["Sprinklr", "Unify Apps", "Tekion","Headout","Oracle"]
    run_pipeline(companies_to_scrape)
    
    print(f"\nTotal records collected: {len(scraped_database)}")

    try:
        dict_database = [record.model_dump() for record in scraped_database]
    except AttributeError:
        dict_database = [record.dict() for record in scraped_database]
    
    with open("django_seed_data.json", "w", encoding="utf-8") as f:
        json.dump(dict_database, f, indent=4, ensure_ascii=False)
        
    print("Data saved to 'django_seed_data.json'. Ready for database ingestion.")