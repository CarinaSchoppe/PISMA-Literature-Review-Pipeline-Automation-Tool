from __future__ import annotations

import unittest

from models.paper import PaperMetadata
from utils.deduplication import deduplicate_papers


class DeduplicationTests(unittest.TestCase):
    def test_merges_same_doi_records(self) -> None:
        papers = [
            PaperMetadata(
                title="Large language models for screening",
                authors=["Alice"],
                abstract="short",
                year=2024,
                doi="10.1000/test",
                source="openalex",
                citation_count=10,
            ),
            PaperMetadata(
                title="Large language models for screening",
                authors=["Bob"],
                abstract="a much longer abstract for the same paper",
                year=2024,
                doi="https://doi.org/10.1000/test",
                source="crossref",
                citation_count=15,
            ),
        ]

        deduplicated = deduplicate_papers(papers)

        self.assertEqual(len(deduplicated), 1)
        self.assertIn("Alice", deduplicated[0].authors)
        self.assertIn("Bob", deduplicated[0].authors)
        self.assertEqual(deduplicated[0].citation_count, 15)
        self.assertEqual(deduplicated[0].abstract, "a much longer abstract for the same paper")

