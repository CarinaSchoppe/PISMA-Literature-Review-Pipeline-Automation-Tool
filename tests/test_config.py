from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from config import ResearchConfig, build_arg_parser, parse_analysis_pass


class ConfigTests(unittest.TestCase):
    def test_finalize_creates_query_key_and_directories(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config = ResearchConfig(
                research_topic="AI literature reviews",
                search_keywords=["llm", "screening"],
                data_dir=root / "data",
                papers_dir=root / "papers",
                results_dir=root / "results",
                database_path=root / "data" / "review.db",
            ).finalize()

            self.assertTrue(config.query_key)
            self.assertTrue((root / "data").exists())
            self.assertTrue((root / "papers").exists())
            self.assertTrue((root / "results").exists())

    def test_from_cli_can_load_complete_config_file(self) -> None:
        parser = build_arg_parser()
        args = parser.parse_args(["--config-file", "tests/fixtures/offline_config.json"])

        with patch("builtins.input", side_effect=AssertionError("input should not be called")):
            config = ResearchConfig.from_cli(args)

        self.assertEqual(config.research_topic, "AI-assisted literature reviews")
        self.assertFalse(config.openalex_enabled)
        self.assertEqual(config.fixture_data_path, Path("tests/fixtures/offline_papers.json"))

    def test_parse_analysis_pass(self) -> None:
        analysis_pass = parse_analysis_pass("deep:heuristic:85:triage:12")

        self.assertEqual(analysis_pass.name, "deep")
        self.assertEqual(analysis_pass.llm_provider, "heuristic")
        self.assertEqual(analysis_pass.threshold, 85.0)
        self.assertEqual(analysis_pass.decision_mode, "triage")
        self.assertEqual(analysis_pass.maybe_threshold_margin, 12.0)

    def test_from_cli_reads_additional_source_flags(self) -> None:
        parser = build_arg_parser()
        args = parser.parse_args(
            [
                "--topic",
                "Evidence discovery",
                "--research-question",
                "Can multiple discovery sources be configured safely?",
                "--review-objective",
                "Compare source configuration options.",
                "--inclusion-criteria",
                "metadata available",
                "--exclusion-criteria",
                "none",
                "--banned-topics",
                "spam",
                "--keywords",
                "llm,review",
                "--boolean",
                "AND",
                "--pages",
                "1",
                "--year-start",
                "2020",
                "--year-end",
                "2026",
                "--max-papers",
                "10",
                "--citation-snowballing",
                "--threshold",
                "70",
                "--no-download-pdfs",
                "--no-analyze-full-text",
                "--springer-enabled",
                "--arxiv-enabled",
                "--no-include-pubmed",
                "--llm-provider",
                "huggingface_local",
                "--openai-model",
                "gpt-5.4",
                "--ollama-model",
                "gpt-oss:20b",
                "--huggingface-model",
                "openai/gpt-oss-20b",
                "--huggingface-max-new-tokens",
                "512",
                "--google-scholar-import-path",
                "tests/fixtures/google_scholar_import.json",
                "--researchgate-import-path",
                "tests/fixtures/researchgate_import.csv",
                "--data-dir",
                "data/test_cli",
                "--papers-dir",
                "papers/test_cli",
                "--results-dir",
                "results/test_cli",
                "--database-path",
                "data/test_cli/review.db",
            ]
        )

        with patch("builtins.input", side_effect=AssertionError("input should not be called")):
            config = ResearchConfig.from_cli(args)

        self.assertTrue(config.springer_enabled)
        self.assertTrue(config.arxiv_enabled)
        self.assertEqual(config.llm_provider, "huggingface_local")
        self.assertEqual(config.api_settings.openai_model, "gpt-5.4")
        self.assertEqual(config.api_settings.ollama_model, "gpt-oss:20b")
        self.assertEqual(config.api_settings.huggingface_model, "openai/gpt-oss-20b")
        self.assertEqual(config.api_settings.huggingface_max_new_tokens, 512)
        self.assertEqual(config.google_scholar_import_path, Path("tests/fixtures/google_scholar_import.json"))
        self.assertEqual(config.researchgate_import_path, Path("tests/fixtures/researchgate_import.csv"))
        self.assertEqual(config.results_dir, Path("results/test_cli"))
