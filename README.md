# PRISMA Literature Review Pipeline

This project implements a production-oriented Python pipeline for systematic literature discovery, metadata consolidation, citation expansion, AI-assisted screening, relevance scoring, and report generation.

The architecture is modular:

- `main.py` handles the interactive CLI entrypoint.
- `config.py` stores all run settings in a validated config object.
- `database.py` persists paper records and screening decisions in SQLite.
- `discovery/` queries OpenAlex, Semantic Scholar, Crossref, and optionally PubMed.
- `acquisition/` enriches metadata and downloads PDFs via Unpaywall or direct OA links.
- `acquisition/` also supports optional PDF full-text extraction for deeper screening.
- `citation/` performs backward and forward snowballing.
- `analysis/` provides two-stage screening with heuristic scoring, multi-pass screening, and pluggable LLM support.
- `pipeline/` orchestrates the full workflow end to end.
- `reporting/` exports configurable CSV, JSON, SQLite, citation graph data, and Markdown summaries.
- `utils/` centralizes normalization, deduplication, and HTTP helpers.

## Project Structure

```text
project_root/
|-- main.py
|-- config.py
|-- database.py
|-- requirements.txt
|-- requirements-local-llm.txt
|-- README.md
|-- sample.ipynb
|-- acquisition/
|   |-- full_text_extractor.py
|   `-- pdf_fetcher.py
|-- analysis/
|   |-- ai_screener.py
|   |-- llm_clients.py
|   `-- relevance_scoring.py
|-- citation/
|   `-- citation_expander.py
|-- discovery/
|   |-- arxiv_client.py
|   |-- crossref_client.py
|   |-- fixture_client.py
|   |-- manual_import_client.py
|   |-- null_citation_provider.py
|   |-- openalex_client.py
|   |-- protocols.py
|   |-- pubmed_client.py
|   |-- springer_client.py
|   `-- semantic_scholar_client.py
|-- models/
|   `-- paper.py
|-- pipeline/
|   `-- pipeline_controller.py
|-- reporting/
|   `-- report_generator.py
|-- tests/
|   |-- fixtures/
|   |-- test_config.py
|   |-- test_deduplication.py
|   |-- test_pipeline_integration.py
|   `-- test_relevance_scoring.py
`-- utils/
    |-- deduplication.py
    |-- http.py
    `-- text_processing.py
```

## Features

- Interactive CLI with validated configuration
- JSON config-file support for repeatable runs
- Parallel discovery requests across academic APIs
- Source-specific toggles for OpenAlex, Semantic Scholar, Crossref, Springer Nature, PubMed, and arXiv
- SQLite persistence for full pipeline state and resume capability
- DOI and title-similarity deduplication
- Optional PubMed inclusion for biomedical topics
- Backward and forward citation snowballing
- Dedicated manual-import entrypoints for Google Scholar and ResearchGate exports
- Unpaywall-powered OA enrichment and PDF download
- Optional full-text PDF extraction with `pypdf`
- `collect` mode for metadata-only runs without screening
- configurable logging verbosity: `quiet`, `normal`, `verbose`, `debug`
- Two-stage screening:
  - Stage 1 quick include/maybe/exclude
  - Stage 2 deep scoring with structured output
- sequential multi-pass screening with pass-specific providers and thresholds
- Optional LLM scoring through OpenAI-compatible chat completions, local Ollama, or local Hugging Face models
- Strict threshold mode for keep-or-exclude workflows
- Banned topic filtering for hard exclusions
- Screening cache to avoid repeat analysis for the same paper and screening context
- Separate included and excluded outputs with reasons
- PRISMA-style flow outputs
- CSV, JSON, Markdown, and citation-graph outputs
- Offline fixture mode for deterministic smoke tests
- `unittest` suite for fast local verification

## Environment Variables

These are optional, but strongly recommended:

- `UNPAYWALL_EMAIL`: required for reliable Unpaywall lookups
- `CROSSREF_MAILTO`: polite contact email for Crossref/OpenAlex requests
- `SEMANTIC_SCHOLAR_API_KEY`: increases Semantic Scholar quota
- `SPRINGER_API_KEY`: required for Springer Nature Metadata API discovery
- `OPENAI_API_KEY`: enables LLM-based screening and review synthesis
- `OPENAI_BASE_URL`: override for OpenAI-compatible endpoints
- `OPENAI_MODEL`: chat model name, default `gpt-5.4`
- `OLLAMA_BASE_URL`: default `http://localhost:11434/v1`
- `OLLAMA_MODEL`: local model name, default `qwen3:8b`
- `OLLAMA_API_KEY`: optional, default `ollama`
- `HF_MODEL_ID`: local Hugging Face model id, default `Qwen/Qwen3-8B`
- `HF_TASK`: Transformers pipeline task, default `text-generation`
- `HF_DEVICE`: device or device-map setting, default `auto`
- `HF_DTYPE`: dtype selection, default `auto`
- `HF_MAX_NEW_TOKENS`: local generation limit, default `700`
- `HF_HOME` or `TRANSFORMERS_CACHE`: optional local cache directory
- `HF_TRUST_REMOTE_CODE`: allow custom model code when needed, default `false`
- `LLM_TEMPERATURE`: shared generation temperature for remote or local LLM runs

Without `OPENAI_API_KEY`, the pipeline still runs using the built-in heuristic scorer.

## Setup

On Windows PowerShell:

```powershell
py -3 -m venv .venv
.venv\Scripts\Activate.ps1
py -3 -m pip install --upgrade pip
py -3 -m pip install -r requirements.txt
```

Optional for local Hugging Face models:

```powershell
py -3 -m pip install -r requirements-local-llm.txt
```

Optional for notebooks:

```powershell
py -3 -m pip install notebook
```

## Run From CLI

Interactive mode:

```powershell
py -3 main.py
```

Example non-interactive run:

```powershell
py -3 main.py `
  --topic "AI-assisted systematic literature reviews" `
  --keywords "LLM,screening,systematic review,information retrieval" `
  --boolean AND `
  --pages 2 `
  --year-start 2020 `
  --year-end 2026 `
  --max-papers 40 `
  --run-mode analyze `
  --verbosity verbose `
  --citation-snowballing `
  --download-pdfs `
  --include-pubmed `
  --threshold 72
```

Metadata-only collection run:

```powershell
py -3 main.py `
  --config-file tests\fixtures\offline_config.json `
  --run-mode collect `
  --no-output-json `
  --no-output-markdown `
  --no-output-sqlite-exports
```

Multi-pass analysis run:

```powershell
py -3 main.py `
  --config-file tests\fixtures\offline_config.json `
  --analysis-pass fast:heuristic:65:strict `
  --analysis-pass deep:ollama:50:triage:10 `
  --verbosity verbose
```

Local Hugging Face run:

```powershell
py -3 main.py --config-file configs\huggingface_local.example.json
```

Local Hugging Face run with OpenAI OSS weights:

```powershell
py -3 main.py --config-file configs\huggingface_gpt_oss.example.json
```

Latest OpenAI flagship run:

```powershell
py -3 main.py --config-file configs\openai_latest.example.json
```

Manual-import run for Google Scholar and ResearchGate exports:

```powershell
py -3 main.py `
  --topic "Evidence discovery workflows" `
  --research-question "Can manual exports from unsupported platforms be merged safely?" `
  --review-objective "Validate import-driven collection mode." `
  --inclusion-criteria "metadata available" `
  --exclusion-criteria "none" `
  --banned-topics "spam" `
  --keywords "llm,systematic review" `
  --boolean AND `
  --pages 1 `
  --year-start 2020 `
  --year-end 2026 `
  --max-papers 5 `
  --citation-snowballing `
  --threshold 60 `
  --no-download-pdfs `
  --no-analyze-full-text `
  --no-include-pubmed `
  --run-mode collect `
  --verbosity verbose `
  --no-openalex-enabled `
  --no-semantic-scholar-enabled `
  --no-crossref-enabled `
  --no-springer-enabled `
  --no-arxiv-enabled `
  --google-scholar-import-path tests\fixtures\google_scholar_import.json `
  --researchgate-import-path tests\fixtures\researchgate_import.csv `
  --results-dir results\manual_import_smoke `
  --data-dir data\manual_import_smoke `
  --papers-dir papers\manual_import_smoke `
  --database-path data\manual_import_smoke\literature_review.db
```

Config-file driven run:

```powershell
py -3 main.py --config-file tests\fixtures\offline_config.json
```

Local Ollama-driven run:

```powershell
py -3 main.py --config-file configs\ollama_local.example.json
```

## Pipeline Order

```text
input -> discovery -> deduplication -> database storage -> citation expansion -> pdf enrichment -> AI screening -> scoring -> ranking -> report generation
```

## Outputs

After a run, the pipeline writes:

- `results/papers.csv`
- `results/included_papers.csv`
- `results/excluded_papers.csv`
- `results/top_papers.json`
- `results/citation_graph.json`
- `results/review_summary.md`
- `results/prisma_flow.json`
- `results/prisma_flow.md`
- `results/included_papers.db`
- `results/excluded_papers.db`
- `results/run_config.json`
- PDFs into `papers/` when download is enabled and OA copies exist

## Testing

Fast local test suite:

```powershell
py -3 -m unittest discover -s tests -v
```

Fast offline smoke test with deterministic fixture data:

```powershell
py -3 main.py --config-file tests\fixtures\offline_config.json
```

That smoke test avoids external APIs and writes into:

- `results/offline_smoke/`
- `data/offline_smoke/`
- `papers/offline_smoke/`

## Important Configuration Flags

- `--config-file`: load a full JSON run configuration
- `--research-question`, `--review-objective`: give the screener explicit review intent
- `--inclusion-criteria`, `--exclusion-criteria`: make screening decisions more reproducible
- `--banned-topics`: hard exclusion themes
- `--results-per-page`: tune per-source pagination size
- `--max-workers`: control screening and discovery concurrency
- `--request-timeout-seconds`: tune API request timeouts
- `--title-similarity-threshold`: control deduplication strictness
- `--openalex-enabled`, `--semantic-scholar-enabled`, `--crossref-enabled`, `--include-pubmed`: choose discovery sources
- `--springer-enabled`, `--arxiv-enabled`: add official Springer Nature and arXiv discovery APIs
- `--google-scholar-import-path`, `--researchgate-import-path`: ingest manual exports from unsupported direct-query platforms
- `--resume-mode`: skip already-screened records on repeated runs
- `--disable-progress-bars`: cleaner logs for CI or tests
- `--fixture-data`: bypass live APIs and use local fixture records
- `--manual-source-path`: import CSV or JSON metadata exports from other systems
- `--data-dir`, `--papers-dir`, `--results-dir`, `--database-path`: relocate state and output paths from the CLI
- `--llm-provider`: select `heuristic`, `openai_compatible`, `ollama`, or `huggingface_local`
- `--openai-model`, `--ollama-model`, `--huggingface-model`: select the actual model backend
- `--huggingface-task`, `--huggingface-device`, `--huggingface-dtype`, `--huggingface-max-new-tokens`, `--huggingface-cache-dir`: tune local HF inference
- `--huggingface-trust-remote-code`: opt into custom model code when needed
- `--run-mode`: `collect` for metadata-only runs or `analyze` for full screening
- `--verbosity`: `quiet`, `normal`, `verbose`, or `debug`
- `--decision-mode`: choose `strict` or `triage`
- `--maybe-threshold-margin`: triage margin below the keep threshold
- `--analysis-pass`: chain multiple screening passes as `name:provider:threshold[:decision_mode[:margin]]`
- `--output-csv`, `--output-json`, `--output-markdown`, `--output-sqlite-exports`: control which result bundles are written
- `--analyze-full-text`, `--full-text-max-chars`: opt into PDF full-text screening

## Scientific Screening Workflow

The pipeline supports a more explicit review setup than a plain keyword search:

- topic
- research question
- review objective
- inclusion criteria
- exclusion criteria
- banned topics
- numeric relevance threshold
- strict or triage decision mode

In `strict` mode the decision rule is simple:

- score >= threshold: keep
- score < threshold: exclude

This is the most reproducible option when you want a hard cut-off such as 85%.

## Keep / Exclude Databases

The pipeline now writes separate SQLite outputs:

- `included_papers.db`
- `excluded_papers.db`

Both keep the bibliographic core fields:

- title
- authors
- year
- venue
- DOI
- source

And also the screening rationale:

- retain reason
- exclusion reason
- matched inclusion criteria
- matched exclusion criteria
- matched banned topics

The main SQLite database also stores a screening cache so the same paper is not re-analyzed for the same screening context unless the context changes.

## Manual Source Imports

If you export metadata from another system into CSV or JSON, you can ingest it with:

```powershell
py -3 main.py --manual-source-path path\to\export.csv --no-openalex-enabled --no-semantic-scholar-enabled --no-crossref-enabled
```

This is the supported way to bring in records from tools or platforms that do not provide a stable public API for this workflow.

For source-specific workflows there are dedicated import flags:

- `--google-scholar-import-path`
- `--researchgate-import-path`

Those imports are tagged in the output database and CSV exports as `google_scholar_import` and `researchgate_import`.

## Jupyter Usage

The repository includes [`sample.ipynb`](./sample.ipynb), which shows how to instantiate `ResearchConfig`, run `PipelineController`, and inspect the exported results inside a notebook.

## LLM Choices

Recommended defaults for this project:

- OpenAI API: `gpt-5.4` for the strongest hosted screening quality.
- Ollama: `qwen3:8b` as the pragmatic default for local CPU/GPU use.
- Hugging Face local: `Qwen/Qwen3-8B` as the default fully local free model.
- Larger local option: `openai/gpt-oss-20b` if you have more VRAM and want a stronger open-weight reasoning model.
- Server-class local option: `meta-llama/Llama-3.3-70B-Instruct` if you have the hardware budget.

Practical guidance:

- If you want the best quality with the least setup, use OpenAI.
- If you want a local model that is easy to run through Ollama, start with Qwen3.
- If you want fully local free inference through Transformers, start with `Qwen/Qwen3-8B`.
- If you want a heavier open-weight model and can afford the hardware, try `openai/gpt-oss-20b`.

The pipeline keeps these choices configurable per run and per analysis pass, so you can do a cheap first pass and a stronger second pass.

## Notes

- Discovery uses APIs only. No scraping is performed.
- Google Scholar is intentionally not queried directly because the project stays API-only and avoids scraping. Based on Google's official Scholar help pages, Scholar exposes search, citation links, related-article navigation, library links, and citation export features in the web UI, but I did not find an official public Scholar API in those sources. This is an inference from the official documentation surface, not a direct quote.
- ResearchGate is also not queried directly. ResearchGate's help center documents OAI-PMH for repository ingestion, and ResearchGate's Terms of Service prohibit robots or scraping on the service. For that reason, the project supports manual import instead of direct ResearchGate crawling.
- Springer Nature and arXiv are now supported as direct discovery sources when their official API endpoints are enabled.
- Full-text analysis is available when PDFs are downloaded and `pypdf` can extract readable text.
- Citation expansion is built on OpenAlex to keep the snowballing layer reproducible and metadata-rich.
- If citation snowballing is enabled but no citation-capable API source is active, the pipeline logs that expansion is skipped and continues without failing.
- Resume behavior is enabled by default and skips already-screened papers for the current query signature.
