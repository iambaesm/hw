import unittest
from datetime import datetime, timezone

from newsbot import (
    Article,
    article_score,
    canonical_url,
    clean_text,
    deduplicate,
    split_telegram_message,
)


COMPANY = {
    "include_any": ["SLL중앙", "콘텐트리중앙"],
    "priority_keywords": ["회사채", "유동성"],
}


class NewsbotTests(unittest.TestCase):
    def test_clean_text_removes_html_and_entities(self):
        self.assertEqual(clean_text("<b>SLL</b>&nbsp;중앙"), "SLL 중앙")

    def test_canonical_url_removes_tracking_query(self):
        self.assertEqual(
            canonical_url("https://www.example.com/a/?utm_source=x"),
            "https://example.com/a",
        )

    def test_priority_keyword_in_title_scores_higher(self):
        high = article_score("SLL중앙 회사채 만기", "", COMPANY)
        low = article_score("SLL중앙 신작 공개", "", COMPANY)
        self.assertGreater(high, low)

    def test_similar_titles_are_deduplicated(self):
        now = datetime.now(timezone.utc)
        articles = [
            Article("SLL중앙 회사채 만기 대응", "a", "https://a.example/1", now, 7),
            Article("SLL중앙, 회사채 만기 대응", "b", "https://b.example/2", now, 7),
        ]
        self.assertEqual(len(deduplicate(articles)), 1)

    def test_message_split_respects_limit(self):
        chunks = split_telegram_message("A" * 12, limit=5)
        self.assertTrue(all(len(chunk) <= 5 for chunk in chunks))
        self.assertEqual("".join(chunks), "A" * 12)


if __name__ == "__main__":
    unittest.main()
