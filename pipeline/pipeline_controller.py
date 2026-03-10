from __future__ import annotations

import logging
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from tqdm import tqdm

from acquisition.full_text_extractor import FullTextExtractor
from acquisition.pdf_fetcher import PDFFetcher
from analysis.ai_screener import AIScreener
from citation.citation_expander import CitationExpander
from config import AnalysisPassConfig, ResearchConfig
from database import DatabaseManager
from discovery.arxiv_client import ArxivClient
from discovery.crossref_client import CrossrefClient
from discovery.fixture_client import FixtureDiscoveryClient
from discovery.manual_import_client import ManualImportClient
from discovery.null_citation_provider import NullCitationProvider
from discovery.openalex_client import OpenAlexClient
from discovery.pubmed_client import PubMedClient
from discovery.semantic_scholar_client import SemanticScholarClient
from discovery.springer_client import SpringerClient
from models.paper import PaperMetadata, ScreeningResult
from reporting.report_generator import ReportGenerator
from utils.deduplication import deduplicate_papers
from utils.text_processing import stable_hash


LOGGER = logging.getLogger(__name__)


class PipelineController:
    def __init__(self, config: ResearchConfig) -> None:
        self.config = config.finalize()
        self.database = DatabaseManager(self.config.database_path)
        self.database.initialize()
        self.fixture_client = FixtureDiscoveryClient(self.config) if self.config.fixture_data_path else None
        self.manual_import_clients = self._build_manual_import_clients()
        self.openalex_client = OpenAlexClient(self.config)
        self.semantic_scholar_client = SemanticScholarClient(self.config)
        self.crossref_client = CrossrefClient(self.config)
        self.springer_client = SpringerClient(self.config)
        self.arxiv_client = ArxivClient(self.config)
        self.pubmed_client = PubMedClient(self.config)
        self.pdf_fetcher = PDFFetcher(self.config)
        self.full_text_extractor = FullTextExtractor(max_chars=self.config.full_text_max_chars)
        self.pass_screeners = self._build_pass_screeners()
        self.ai_screener = self._summary_screener()
        citation_provider = self.fixture_client or (self.openalex_client if self.config.openalex_enabled else NullCitationProvider())
        self.citation_expander = CitationExpander(self.config, self.database, citation_provider)
        self.report_generator = ReportGenerator(self.config, self.ai_screener)
        if self.config.citation_snowballing_enabled and isinstance(citation_provider, NullCitationProvider):
            LOGGER.info("Citation snowballing is enabled, but no citation-capable API source is active; skipping expansion.")
        if self._requires_local_llm_serial_execution():
            LOGGER.info("Local Hugging Face inference is active; screening parallelism is reduced to 1 worker.")

    def run(self) -> dict[str, str | int]:
        try:
            LOGGER.info(
                "Starting literature pipeline in %s mode for topic '%s'.",
                self.config.run_mode,
                self.config.research_topic,
            )
            self._log_verbose("Search query: %s", self.config.search_query)
            self.config.save_snapshot()
            discovered = self._discover()
            LOGGER.info("Discovery completed with %s records.", len(discovered))
            deduplicated = deduplicate_papers(
                discovered,
                title_similarity_threshold=self.config.title_similarity_threshold,
            )
            LOGGER.info("Deduplication completed with %s unique records.", len(deduplicated))
            stored = self.database.upsert_papers(deduplicated, self.config.query_key or "")
            self._log_verbose("Stored %s records in SQLite.", len(stored))

            expanded = self.citation_expander.expand(stored)
            if expanded:
                LOGGER.info("Citation snowballing discovered %s additional records.", len(expanded))
                expanded_deduplicated = deduplicate_papers(
                    expanded,
                    title_similarity_threshold=self.config.title_similarity_threshold,
                )
                self.database.upsert_papers(expanded_deduplicated, self.config.query_key or "")
            elif self.config.citation_snowballing_enabled:
                self._log_verbose("Citation snowballing returned no additional records.")

            current_papers = self.database.get_papers_for_query(self.config.query_key or "")
            self._log_verbose("Loaded %s records for enrichment.", len(current_papers))
            enriched_papers = self._enrich_with_pdfs(current_papers)
            if enriched_papers:
                self.database.upsert_papers(enriched_papers, self.config.query_key or "")

            if self.config.run_mode == "collect":
                LOGGER.info("Run mode is collect; AI screening is skipped.")
                screening_stats = {"screened_count": 0, "full_text_screened_count": 0}
            else:
                screening_stats = self._screen_papers()
            final_papers = self._normalize_papers_for_current_context(
                self.database.get_papers_for_query(self.config.query_key or "")
            )
            stats = {
                "discovered_count": len(discovered),
                "deduplicated_count": len(deduplicated),
                "snowballing_added_count": len(expanded) if expanded else 0,
                "decision_counts": self._decision_counts(final_papers),
                "screened_count": len([paper for paper in final_papers if paper.inclusion_decision]),
                "newly_screened_count": screening_stats["screened_count"],
                "full_text_screened_count": screening_stats["full_text_screened_count"],
                "run_mode": self.config.run_mode,
            }
            report_paths = self.report_generator.generate(final_papers, stats=stats)
            return {
                **report_paths,
                "discovered_count": len(discovered),
                "deduplicated_count": len(deduplicated),
                "database_count": self.database.count_papers(self.config.query_key or ""),
            }
        finally:
            self.close()

    def close(self) -> None:
        self.database.close()

    def _discover(self) -> list[PaperMetadata]:
        if self.fixture_client:
            self._log_verbose("Loading discovery records from fixture file %s.", self.config.fixture_data_path)
            return self.fixture_client.search()
        imported: list[PaperMetadata] = []
        for manual_client in self.manual_import_clients:
            self._log_verbose("Importing discovery records from %s.", manual_client.path)
            imported.extend(manual_client.search())

        discovered: list[PaperMetadata] = list(imported)
        clients = self._build_discovery_clients(allow_empty=bool(imported))
        if not clients:
            return discovered
        with ThreadPoolExecutor(max_workers=min(self.config.max_workers, len(clients))) as executor:
            future_map = {
                executor.submit(self._discover_from_source, name, callable_): name
                for name, callable_ in clients.items()
            }
            for future in tqdm(
                as_completed(future_map),
                total=len(future_map),
                desc="Discovery sources",
                unit="source",
                disable=self.config.disable_progress_bars,
            ):
                source_name = future_map[future]
                try:
                    discovered.extend(future.result())
                except Exception as exc:  # noqa: BLE001
                    LOGGER.exception("Discovery failed for %s: %s", source_name, exc)
        return discovered

    def _build_discovery_clients(self, *, allow_empty: bool = False) -> dict[str, Callable[[], list[PaperMetadata]]]:
        clients: dict[str, Callable[[], list[PaperMetadata]]] = {}
        if self.config.openalex_enabled:
            clients["openalex"] = self.openalex_client.search
        if self.config.semantic_scholar_enabled:
            clients["semantic_scholar"] = self.semantic_scholar_client.search
        if self.config.crossref_enabled:
            clients["crossref"] = self.crossref_client.search
        if self.config.springer_enabled:
            clients["springer"] = self.springer_client.search
        if self.config.arxiv_enabled:
            clients["arxiv"] = self.arxiv_client.search
        if self.config.include_pubmed:
            clients["pubmed"] = self.pubmed_client.search
        if not clients and not allow_empty:
            raise ValueError("At least one discovery source must be enabled")
        return clients

    def _enrich_with_pdfs(self, papers: list[PaperMetadata]) -> list[PaperMetadata]:
        enriched: list[PaperMetadata] = []
        self._log_verbose("Checking PDF availability for %s papers.", len(papers))
        for paper in tqdm(
            papers,
            desc="PDF metadata and downloads",
            unit="paper",
            disable=self.config.disable_progress_bars,
        ):
            if paper.pdf_path or (paper.pdf_link and not self.config.download_pdfs):
                enriched.append(paper)
                continue
            try:
                self._log_debug("Fetching PDF metadata for '%s'.", paper.title)
                enriched.append(self.pdf_fetcher.fetch_for_paper(paper))
            except Exception as exc:  # noqa: BLE001
                LOGGER.warning("PDF enrichment failed for %s: %s", paper.title, exc)
                enriched.append(paper)
        return enriched

    def _screen_papers(self) -> dict[str, int]:
        if not self.config.resolved_analysis_passes:
            return {"screened_count": 0, "full_text_screened_count": 0}
        candidates = self.database.get_papers_for_analysis(
            self.config.query_key or "",
            self.config.max_papers_to_analyze,
            resume_mode=self.config.resume_mode,
            screening_context_key=self.config.screening_context_key,
        )
        if not candidates:
            LOGGER.info("No papers require screening for the current context.")
            return {"screened_count": 0, "full_text_screened_count": 0}

        LOGGER.info("Preparing %s papers for screening.", len(candidates))
        prepared_candidates = [self._prepare_paper_for_screening(paper) for paper in candidates]
        full_text_screened_count = len(
            [paper for paper in prepared_candidates if paper.raw_payload.get("full_text_excerpt")]
        )
        results: list[tuple[int, ScreeningResult, dict[str, Any]]] = []
        cached_results: list[tuple[int, ScreeningResult, dict[str, Any]]] = []
        uncached_candidates: list[PaperMetadata] = []
        for paper in prepared_candidates:
            if paper.database_id is None:
                continue
            cache_key = self._paper_cache_key(paper)
            cached = self.database.get_cached_screening_entry(cache_key, self.config.screening_context_key)
            if cached is None:
                uncached_candidates.append(paper)
            else:
                cached_results.append((paper.database_id, cached[0], cached[1]))

        if cached_results:
            LOGGER.info("Reused %s cached screening results.", len(cached_results))

        screening_workers = self._screening_worker_count()
        with ThreadPoolExecutor(max_workers=screening_workers) as executor:
            future_map = {
                executor.submit(self._screen_paper_with_passes, paper): paper
                for paper in uncached_candidates
                if paper.database_id is not None
            }
            for future in tqdm(
                as_completed(future_map),
                total=len(future_map),
                desc="AI screening",
                unit="paper",
                disable=self.config.disable_progress_bars,
            ):
                paper = future_map[future]
                try:
                    result, screening_details = future.result()
                    self.database.cache_screening_result(
                        paper=paper,
                        paper_cache_key=self._paper_cache_key(paper),
                        screening_context_key=self.config.screening_context_key,
                        result=result,
                        screening_details=screening_details,
                    )
                    results.append((paper.database_id or 0, result, screening_details))
                except Exception as exc:  # noqa: BLE001
                    LOGGER.exception("Screening failed for %s: %s", paper.title, exc)

        for database_id, result, screening_details in [*cached_results, *results]:
            self.database.update_screening_result(database_id, result, screening_details=screening_details)
        return {
            "screened_count": len(cached_results) + len(results),
            "full_text_screened_count": full_text_screened_count,
        }

    def _prepare_paper_for_screening(self, paper: PaperMetadata) -> PaperMetadata:
        if not self.config.analyze_full_text or not paper.pdf_path:
            return paper
        full_text_excerpt = self.full_text_extractor.extract_excerpt(paper.pdf_path)
        if not full_text_excerpt:
            return paper
        return paper.model_copy(update={"raw_payload": {**paper.raw_payload, "full_text_excerpt": full_text_excerpt}})

    def _screen_paper_with_passes(self, paper: PaperMetadata) -> tuple[ScreeningResult, dict[str, Any]]:
        passes: dict[str, dict[str, Any]] = {}
        final_result: ScreeningResult | None = None
        final_pass_name = ""
        for analysis_pass in self.config.resolved_analysis_passes:
            self._log_verbose(
                "Analyzing '%s' with pass '%s' using %s.",
                paper.title,
                analysis_pass.name,
                analysis_pass.llm_provider,
            )
            screener = self.pass_screeners.get(analysis_pass.name)
            if screener is None:
                screener = AIScreener(self._config_for_analysis_pass(analysis_pass))
            result = screener.screen(paper).model_copy(update={"screening_context_key": self.config.screening_context_key})
            passes[analysis_pass.name] = {
                **result.model_dump(mode="json"),
                "threshold": analysis_pass.threshold,
                "decision_mode": analysis_pass.decision_mode,
                "llm_provider": analysis_pass.llm_provider,
            }
            final_result = result
            final_pass_name = analysis_pass.name

        if final_result is None:
            raise ValueError("At least one analysis pass must be configured in analyze mode")

        screening_details = {
            **final_result.model_dump(mode="json"),
            "screening_context_key": self.config.screening_context_key,
            "final_pass": final_pass_name,
            "passes": passes,
        }
        return final_result, screening_details

    def _paper_cache_key(self, paper: PaperMetadata) -> str:
        fingerprint = stable_hash(
            "|".join(
                [
                    paper.identity_key,
                    paper.title,
                    paper.abstract,
                    paper.raw_payload.get("full_text_excerpt", ""),
                ]
            ),
            length=32,
        )
        return f"{paper.identity_key}|{fingerprint}"

    def _normalize_papers_for_current_context(self, papers: list[PaperMetadata]) -> list[PaperMetadata]:
        normalized: list[PaperMetadata] = []
        for paper in papers:
            context_key = paper.screening_details.get("screening_context_key")
            if context_key == self.config.screening_context_key:
                normalized.append(paper)
                continue
            normalized.append(
                paper.model_copy(
                    update={
                        "relevance_score": None,
                        "relevance_explanation": None,
                        "inclusion_decision": None,
                        "extracted_passage": None,
                        "methodology_category": None,
                        "domain_category": None,
                        "screening_details": {},
                    }
                )
            )
        return normalized

    def _decision_counts(self, papers: list[PaperMetadata]) -> dict[str, int]:
        counts = {"include": 0, "exclude": 0, "maybe": 0, "unreviewed": 0}
        for paper in papers:
            decision = paper.inclusion_decision or "unreviewed"
            counts[decision] = counts.get(decision, 0) + 1
        return counts

    def _discover_from_source(
        self,
        source_name: str,
        search_callable: Callable[[], list[PaperMetadata]],
    ) -> list[PaperMetadata]:
        self._log_verbose("Querying %s.", source_name)
        records = search_callable()
        self._log_verbose("%s returned %s records.", source_name, len(records))
        return records

    def _config_for_analysis_pass(self, analysis_pass: AnalysisPassConfig) -> ResearchConfig:
        return self.config.model_copy(
            update={
                "llm_provider": analysis_pass.llm_provider,
                "relevance_threshold": analysis_pass.threshold,
                "decision_mode": analysis_pass.decision_mode,
                "maybe_threshold_margin": analysis_pass.maybe_threshold_margin,
            }
        )

    def _summary_config(self) -> ResearchConfig:
        resolved_passes = self.config.resolved_analysis_passes
        if not resolved_passes:
            return self.config
        return self._config_for_analysis_pass(resolved_passes[-1])

    def _build_pass_screeners(self) -> dict[str, AIScreener]:
        screeners: dict[str, AIScreener] = {}
        for analysis_pass in self.config.resolved_analysis_passes:
            screeners[analysis_pass.name] = AIScreener(self._config_for_analysis_pass(analysis_pass))
        return screeners

    def _summary_screener(self) -> AIScreener:
        resolved_passes = self.config.resolved_analysis_passes
        if not resolved_passes:
            return AIScreener(self.config)
        return self.pass_screeners[resolved_passes[-1].name]

    def _requires_local_llm_serial_execution(self) -> bool:
        return any(
            analysis_pass.llm_provider == "huggingface_local"
            for analysis_pass in self.config.resolved_analysis_passes
        )

    def _screening_worker_count(self) -> int:
        if self._requires_local_llm_serial_execution():
            return 1
        return self.config.max_workers

    def _log_verbose(self, message: str, *args: Any) -> None:
        if self.config.verbosity in {"verbose", "debug"}:
            LOGGER.info(message, *args)

    def _log_debug(self, message: str, *args: Any) -> None:
        if self.config.verbosity == "debug":
            LOGGER.debug(message, *args)

    def _build_manual_import_clients(self) -> list[ManualImportClient]:
        clients: list[ManualImportClient] = []
        import_specs = [
            (self.config.manual_source_path, "manual_import"),
            (self.config.google_scholar_import_path, "google_scholar_import"),
            (self.config.researchgate_import_path, "researchgate_import"),
        ]
        for path, source_name in import_specs:
            if path:
                clients.append(ManualImportClient(self.config, path=path, source_name=source_name))
        return clients
