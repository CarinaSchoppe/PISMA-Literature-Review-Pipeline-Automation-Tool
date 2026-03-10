"""Unit tests for source-specific metadata parsing logic."""

from __future__ import annotations

import unittest
import xml.etree.ElementTree as ET

from config import ResearchConfig
from discovery.arxiv_client import ArxivClient
from discovery.springer_client import SpringerClient


class DiscoveryClientTests(unittest.TestCase):
    """Validate that representative API payloads normalize into the shared paper model."""

    def test_arxiv_client_parses_atom_entry(self) -> None:
        config = ResearchConfig(
            research_topic="Evidence discovery",
            search_keywords=["llm", "review"],
            arxiv_enabled=True,
            openalex_enabled=False,
            semantic_scholar_enabled=False,
            crossref_enabled=False,
            include_pubmed=False,
        ).finalize()
        client = ArxivClient(config)
        payload = """
        <entry xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
          <id>http://arxiv.org/abs/2501.12345v1</id>
          <updated>2025-01-20T00:00:00Z</updated>
          <published>2025-01-18T00:00:00Z</published>
          <title>LLMs for Evidence Discovery</title>
          <summary>We study literature screening and evidence discovery workflows.</summary>
          <author><name>Alice Example</name></author>
          <author><name>Bob Example</name></author>
          <link href="http://arxiv.org/abs/2501.12345v1" rel="alternate" type="text/html"/>
          <link title="pdf" href="http://arxiv.org/pdf/2501.12345v1" rel="related" type="application/pdf"/>
          <arxiv:doi>10.2000/arxiv-example</arxiv:doi>
          <arxiv:primary_category term="cs.IR"/>
        </entry>
        """

        entry = ET.fromstring(payload)
        paper = client._parse_entry(entry)

        self.assertIsNotNone(paper)
        assert paper is not None
        self.assertEqual(paper.title, "LLMs for Evidence Discovery")
        self.assertEqual(paper.source, "arxiv")
        self.assertEqual(paper.external_ids["arxiv"], "2501.12345v1")
        self.assertEqual(paper.external_ids["category"], "cs.IR")
        self.assertTrue(paper.open_access)

    def test_springer_client_parses_record(self) -> None:
        config = ResearchConfig(
            research_topic="Evidence discovery",
            search_keywords=["llm", "review"],
            springer_enabled=True,
            openalex_enabled=False,
            semantic_scholar_enabled=False,
            crossref_enabled=False,
            include_pubmed=False,
        ).finalize()
        client = SpringerClient(config)
        payload = {
            "title": "Springer metadata example",
            "creators": [{"creator": "Clara Example"}, {"creator": "David Example"}],
            "abstract": "<p>Structured metadata for systematic review automation.</p>",
            "publicationName": "Springer Journal of Reviews",
            "publicationDate": "2024-03-01",
            "doi": "10.2000/springer-example",
            "openaccess": "true",
            "url": [
                {"format": "html", "value": "https://example.org/html"},
                {"format": "pdf", "value": "https://example.org/paper.pdf"},
            ],
        }

        paper = client._parse_record(payload)

        self.assertEqual(paper.title, "Springer metadata example")
        self.assertEqual(paper.source, "springer")
        self.assertEqual(paper.year, 2024)
        self.assertEqual(paper.pdf_link, "https://example.org/paper.pdf")
        self.assertIn("systematic review automation", paper.abstract)
