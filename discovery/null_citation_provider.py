"""No-op citation provider used when no citation-capable backend is enabled."""

from __future__ import annotations

from models.paper import PaperMetadata


def fetch_citations() -> list[PaperMetadata]:
    """Return no citing papers."""

    return []


def fetch_references() -> list[PaperMetadata]:
    """Return no references."""

    return []


class NullCitationProvider:
    """Return empty citation expansions while preserving the citation provider interface."""

    def __init__(self):
        pass
