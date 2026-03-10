from __future__ import annotations

from models.paper import PaperMetadata


class NullCitationProvider:
    def fetch_references(self, paper: PaperMetadata, limit: int = 20) -> list[PaperMetadata]:
        return []

    def fetch_citations(self, paper: PaperMetadata, limit: int = 20) -> list[PaperMetadata]:
        return []
