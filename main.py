from __future__ import annotations

import logging

from config import ResearchConfig, build_arg_parser
from pipeline.pipeline_controller import PipelineController


def configure_logging(level_name: str) -> None:
    level_map = {
        "quiet": logging.WARNING,
        "normal": logging.INFO,
        "verbose": logging.INFO,
        "debug": logging.DEBUG,
    }
    logging.basicConfig(
        level=level_map.get(level_name, logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


def main() -> int:
    parser = build_arg_parser()
    args = parser.parse_args()
    config = ResearchConfig.from_cli(args)
    configure_logging(config.verbosity)
    controller = PipelineController(config)
    result = controller.run()

    print("\nPipeline completed.")
    print(f"Run mode: {config.run_mode}")
    print(f"Verbosity: {config.verbosity}")
    print(f"Discovered records: {result['discovered_count']}")
    print(f"Deduplicated records: {result['deduplicated_count']}")
    print(f"Database records for this query: {result['database_count']}")
    output_labels = {
        "papers_csv": "CSV summary",
        "included_papers_csv": "Included papers CSV",
        "excluded_papers_csv": "Excluded papers CSV",
        "top_papers_json": "Top papers JSON",
        "citation_graph_json": "Citation graph JSON",
        "prisma_flow_json": "PRISMA flow JSON",
        "prisma_flow_md": "PRISMA flow Markdown",
        "included_papers_db": "Included papers DB",
        "excluded_papers_db": "Excluded papers DB",
        "review_summary_md": "Review summary",
    }
    for key, label in output_labels.items():
        if key in result:
            print(f"{label}: {result[key]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
