"""No-op citation provider used when no citation-capable backend is enabled."""

from __future__ import annotations

from models.paper import PaperMetadata


class NullCitationProvider:
    """Return empty citation expansions while preserving the citation provider interface."""

    def fetch_references(self, paper: PaperMetadata, limit: int = 20) -> list[PaperMetadata]:
        """Return no references."""

        return []

    def fetch_citations(self, paper: PaperMetadata, limit: int = 20) -> list[PaperMetadata]:
        """Return no citing papers."""

        return []
