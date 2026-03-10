"""Typing protocols for pluggable discovery and citation backends."""

from __future__ import annotations

from typing import Protocol

from models.paper import PaperMetadata


class DiscoveryClientProtocol(Protocol):
    """Protocol for clients that can discover papers from an external source."""

    def search(self) -> list[PaperMetadata]:
        ...


class CitationProviderProtocol(Protocol):
    """Protocol for clients that can expand references and citations around a paper."""

    def fetch_references(self, paper: PaperMetadata, limit: int = 20) -> list[PaperMetadata]:
        ...

    def fetch_citations(self, paper: PaperMetadata, limit: int = 20) -> list[PaperMetadata]:
        ...
