from __future__ import annotations

from typing import Protocol

from models.paper import PaperMetadata


class DiscoveryClientProtocol(Protocol):
    def search(self) -> list[PaperMetadata]:
        ...


class CitationProviderProtocol(Protocol):
    def fetch_references(self, paper: PaperMetadata, limit: int = 20) -> list[PaperMetadata]:
        ...

    def fetch_citations(self, paper: PaperMetadata, limit: int = 20) -> list[PaperMetadata]:
        ...

