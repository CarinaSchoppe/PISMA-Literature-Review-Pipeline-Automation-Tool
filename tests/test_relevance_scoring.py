from __future__ import annotations

import unittest

from analysis.relevance_scoring import RelevanceScorer
from config import ResearchConfig
from models.paper import PaperMetadata


class RelevanceScoringTests(unittest.TestCase):
    def test_scores_relevant_review_paper_highly(self) -> None:
        config = ResearchConfig(
            research_topic="AI-assisted literature reviews",
            research_question="Can LLMs help with screening?",
            review_objective="Keep relevant screening papers only",
            inclusion_criteria=["systematic review screening"],
            exclusion_criteria=["agriculture only"],
            search_keywords=["large language models", "screening", "systematic review"],
            relevance_threshold=55,
            decision_mode="strict",
            include_pubmed=False,
        ).finalize()
        scorer = RelevanceScorer(config)
        paper = PaperMetadata(
            title="Large language models for systematic review screening",
            authors=["Alice Example"],
            abstract=(
                "This systematic review evaluates large language models for abstract screening, "
                "evidence synthesis, and methodological support in PRISMA workflows."
            ),
            year=2024,
            venue="Review Science",
            citation_count=150,
            source="fixture",
        )

        quick_decision = scorer.quick_screen(paper)
        result = scorer.deep_score(paper, stage_one_decision=quick_decision)

        self.assertEqual(quick_decision, "include")
        self.assertGreaterEqual(result.relevance_score, 55)
        self.assertEqual(result.methodology_category, "systematic review")
        self.assertEqual(result.decision, "include")

    def test_excludes_banned_topic(self) -> None:
        config = ResearchConfig(
            research_topic="AI-assisted literature reviews",
            search_keywords=["large language models", "screening"],
            banned_topics=["crop irrigation"],
            relevance_threshold=55,
            decision_mode="strict",
            include_pubmed=False,
        ).finalize()
        scorer = RelevanceScorer(config)
        paper = PaperMetadata(
            title="Crop irrigation optimization with large language models",
            authors=["Farah Agriculture"],
            abstract="This work studies crop irrigation control and plant growth using large language models.",
            year=2024,
            venue="Agricultural Systems",
            citation_count=10,
            source="fixture",
        )

        result = scorer.deep_score(paper, stage_one_decision=scorer.quick_screen(paper))

        self.assertEqual(result.decision, "exclude")
        self.assertIn("crop irrigation", " ".join(result.matched_banned_topics).lower())
