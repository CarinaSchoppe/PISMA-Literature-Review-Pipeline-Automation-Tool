"""Tests for LLM-screening fallback behavior and structured parsing guards."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from models.paper import PaperMetadata

from analysis.ai_screener import AIScreener
from config import ResearchConfig


class _FakeEnabledLLMClient:
    """Enabled fake LLM client that returns a configurable raw text response."""

    enabled = True

    def __init__(self, response_text: str) -> None:
        self.response_text = response_text

    def chat(self, *, system_prompt: str, user_prompt: str):  # noqa: ANN001
        class _Response:
            def __init__(self, content: str) -> None:
                self.content = content

        return _Response(self.response_text)


class AIScreenerTests(unittest.TestCase):
    """Verify that malformed LLM outputs do not overwrite heuristic screening results."""

    def test_invalid_stage_two_json_falls_back_to_heuristic_scoring(self) -> None:
        config = ResearchConfig(
            research_topic="AI-assisted literature reviews",
            search_keywords=["large language models", "screening", "systematic review"],
            llm_provider="openai_compatible",
            relevance_threshold=50,
            include_pubmed=False,
        ).finalize()
        paper = PaperMetadata(
            title="Large language models for systematic review screening",
            abstract="We evaluate LLM support for systematic review screening workflows.",
            year=2024,
            citation_count=42,
        )

        with patch(
                "analysis.ai_screener.build_llm_client",
                return_value=_FakeEnabledLLMClient("This is not strict JSON."),
        ):
            screener = AIScreener(config)
            result = screener.screen(paper)
            expected = screener.scorer.deep_score(
                paper,
                stage_one_decision=screener.scorer.quick_screen(paper),
            )

        self.assertEqual(result.relevance_score, expected.relevance_score)
        self.assertEqual(result.decision, expected.decision)
        self.assertIn("Topic match", result.explanation)


if __name__ == "__main__":
    unittest.main()
