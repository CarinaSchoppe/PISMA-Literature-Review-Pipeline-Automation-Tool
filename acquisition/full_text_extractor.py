"""Helpers for extracting bounded full-text excerpts from downloaded PDFs."""

from __future__ import annotations

import logging
from pathlib import Path

LOGGER = logging.getLogger(__name__)


class FullTextExtractor:
    """Read PDFs and return a truncated text excerpt for screening."""

    def __init__(self, max_chars: int = 12000) -> None:
        self.max_chars = max_chars

    def extract_excerpt(self, pdf_path: str | Path | None) -> str | None:
        """Extract text up to the configured character budget from a local PDF file."""

        if not pdf_path:
            return None
        try:
            from pypdf import PdfReader
        except ImportError:
            LOGGER.warning("pypdf is not installed; skipping full-text extraction")
            return None

        path = Path(pdf_path)
        if not path.exists():
            return None

        try:
            reader = PdfReader(str(path))
            chunks: list[str] = []
            total_chars = 0
            for page in reader.pages:
                page_text = (page.extract_text() or "").strip()
                if not page_text:
                    continue
                remaining = self.max_chars - total_chars
                if remaining <= 0:
                    break
                chunks.append(page_text[:remaining])
                total_chars += len(chunks[-1])
                if total_chars >= self.max_chars:
                    break
            if not chunks:
                return None
            return "\n\n".join(chunks)
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("Failed to extract PDF text from %s: %s", path, exc)
            return None
