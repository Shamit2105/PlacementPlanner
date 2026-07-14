from unittest.mock import Mock, patch

from django.test import SimpleTestCase

from .models import QuestionSource
from .scraper import PageFetcher, QuestionScraper


class QuestionScraperTests(SimpleTestCase):
    def test_accepts_only_leetcode_discuss_urls(self):
        scraper = object.__new__(QuestionScraper)

        self.assertEqual(
            scraper._source_for_url(
                "https://leetcode.com/discuss/interview-experience/123/example"
            ),
            QuestionSource.LEETCODE,
        )
        self.assertEqual(
            scraper._source_for_url("https://leetcode.com/problems/two-sum/"), ""
        )
        self.assertEqual(
            scraper._source_for_url("https://notleetcode.com/discuss/123"), ""
        )

    def test_requires_requested_company_in_scraped_content(self):
        scraper = object.__new__(QuestionScraper)
        scraper.search_client = Mock()
        scraper.search_client.search.return_value = [
            {"link": "https://leetcode.com/discuss/interview-experience/123/amazon"},
            {"link": "https://leetcode.com/discuss/interview-experience/456/google"},
        ]
        scraper.fetcher = Mock()
        scraper.fetcher.fetch_text.side_effect = lambda url: (
            "Amazon interview experience " * 10
            if "amazon" in url
            else "Google interview experience " * 10
        )

        experiences = scraper.scrape_experiences(company="Amazon", target_count=2)

        self.assertEqual(len(experiences), 1)
        self.assertIn("amazon", experiences[0]["source_url"])

    def test_company_match_handles_spaces_and_punctuation(self):
        self.assertTrue(
            QuestionScraper._matches_company("I interviewed at Unify-Apps.", "Unify Apps")
        )
        self.assertFalse(
            QuestionScraper._matches_company("I interviewed at Another Apps.", "Unify Apps")
        )


class PageFetcherTests(SimpleTestCase):
    @patch.object(
        PageFetcher, "_fetch_html_text", return_value="fallback interview content"
    )
    @patch("companies.scraper.requests.post")
    def test_leetcode_uses_html_fallback_for_graphql_errors(self, post, html_fallback):
        response = Mock()
        response.json.return_value = {"errors": [{"message": "Forbidden"}]}
        post.return_value = response

        text = PageFetcher()._fetch_leetcode_text(
            "https://leetcode.com/discuss/interview-experience/123/example"
        )

        self.assertEqual(text, "fallback interview content")
        html_fallback.assert_called_once()

# Create your tests here.
