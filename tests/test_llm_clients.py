"""Tests for the pluggable LLM client adapters used by the screening layer."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from analysis.llm_clients import build_llm_client
from config import ResearchConfig


class _FakeGenerator:
    """Minimal fake text-generation pipeline used to isolate the HF client adapter."""

    def __init__(self) -> None:
        self.calls: list[tuple[object, dict[str, object]]] = []

    def __call__(self, messages: object, **kwargs: object) -> list[dict[str, object]]:
        self.calls.append((messages, kwargs))
        return [
            {
                "generated_text": [
                    {"role": "system", "content": "stub"},
                    {"role": "assistant", "content": "{\"decision\": \"include\"}"},
                ]
            }
        ]


class _FakeTorch:
    """Subset of torch dtypes needed by the local HF client tests."""

    float16 = "float16"
    bfloat16 = "bfloat16"


class LLMClientTests(unittest.TestCase):
    """Exercise local-runtime success and fallback behavior for LLM client creation."""

    def test_build_huggingface_client_uses_local_runtime(self) -> None:
        fake_generator = _FakeGenerator()

        def fake_pipeline(**kwargs: object) -> _FakeGenerator:
            self.assertEqual(kwargs["model"], "Qwen/Qwen3-8B")
            self.assertEqual(kwargs["task"], "text-generation")
            return fake_generator

        config = ResearchConfig(
            research_topic="AI-assisted literature reviews",
            search_keywords=["llm", "screening"],
            llm_provider="huggingface_local",
            include_pubmed=False,
            api_settings={
                "huggingface_model": "Qwen/Qwen3-8B",
                "huggingface_task": "text-generation",
                "huggingface_max_new_tokens": 256,
            },
        ).finalize()

        with patch("analysis.llm_clients.load_transformers_runtime", return_value=(_FakeTorch, fake_pipeline)):
            client = build_llm_client(config)
            response = client.chat(system_prompt="system", user_prompt="user")

        self.assertTrue(client.enabled)
        self.assertEqual(client.provider_name, "huggingface_local")
        self.assertEqual(response.content, "{\"decision\": \"include\"}")
        self.assertEqual(fake_generator.calls[0][1]["max_new_tokens"], 256)

    def test_build_huggingface_client_falls_back_when_runtime_missing(self) -> None:
        config = ResearchConfig(
            research_topic="AI-assisted literature reviews",
            search_keywords=["llm", "screening"],
            llm_provider="huggingface_local",
            include_pubmed=False,
        ).finalize()

        with patch("analysis.llm_clients.load_transformers_runtime", side_effect=RuntimeError("missing runtime")):
            client = build_llm_client(config)

        self.assertFalse(client.enabled)
        self.assertEqual(client.provider_name, "huggingface_local")
