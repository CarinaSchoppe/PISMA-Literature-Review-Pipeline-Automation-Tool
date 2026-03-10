from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Iterable, Iterator, Sequence


WHITESPACE_RE = re.compile(r"\s+")
TAG_RE = re.compile(r"<[^>]+>")
NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")
STOPWORDS = {
    "about",
    "after",
    "also",
    "among",
    "between",
    "from",
    "into",
    "over",
    "that",
    "their",
    "there",
    "these",
    "this",
    "through",
    "towards",
    "using",
    "with",
}


def canonical_doi(value: str) -> str:
    cleaned = value.strip().lower()
    cleaned = cleaned.replace("https://doi.org/", "").replace("http://doi.org/", "")
    cleaned = cleaned.replace("doi:", "").strip()
    return cleaned


def normalize_text(value: str) -> str:
    return WHITESPACE_RE.sub(" ", str(value or "")).strip()


def normalize_title(value: str) -> str:
    cleaned = normalize_text(value).lower()
    return NON_ALNUM_RE.sub(" ", cleaned).strip()


def strip_markup(value: str) -> str:
    text = TAG_RE.sub(" ", str(value or ""))
    return normalize_text(text)


def reconstruct_inverted_abstract(index: dict[str, list[int]] | None) -> str:
    if not index:
        return ""
    size = 1 + max(position for positions in index.values() for position in positions)
    tokens = [""] * size
    for token, positions in index.items():
        for position in positions:
            tokens[position] = token
    return normalize_text(" ".join(tokens))


def build_query(topic: str, keywords: Sequence[str], boolean_expression: str | None = None) -> str:
    cleaned_keywords = [keyword.strip() for keyword in keywords if keyword.strip()]
    if boolean_expression:
        operator = boolean_expression.strip().upper()
        if operator in {"AND", "OR", "NOT"} and cleaned_keywords:
            return f"{topic.strip()} {operator} " + f" {operator} ".join(cleaned_keywords)
        return normalize_text(f"{topic} {boolean_expression} {' '.join(cleaned_keywords)}")
    if cleaned_keywords:
        return f"{topic.strip()} AND " + " AND ".join(cleaned_keywords)
    return topic.strip()


def keyword_overlap_score(text: str, keywords: Sequence[str]) -> float:
    normalized = normalize_title(text)
    if not normalized or not keywords:
        return 0.0
    hits = 0
    valid_keywords = [keyword for keyword in keywords if keyword.strip()]
    for keyword in valid_keywords:
        normalized_keyword = normalize_title(keyword)
        if normalized_keyword and normalized_keyword in normalized:
            hits += 1
    return hits / max(len(valid_keywords), 1)


def extract_salient_sentence(text: str, keywords: Sequence[str]) -> str:
    sentences = re.split(r"(?<=[.!?])\s+", normalize_text(text))
    if not sentences:
        return ""
    ranked = sorted(
        sentences,
        key=lambda sentence: (
            keyword_overlap_score(sentence, keywords),
            len(sentence),
        ),
        reverse=True,
    )
    return ranked[0][:600]


def safe_year(value: object) -> int | None:
    if value is None or value == "":
        return None
    try:
        year = int(value)
    except (TypeError, ValueError):
        return None
    if 1800 <= year <= 2100:
        return year
    return None


def chunked(values: Sequence[str], size: int) -> Iterator[list[str]]:
    for index in range(0, len(values), size):
        yield list(values[index : index + size])


def make_query_key(topic: str, keywords: Sequence[str], year_start: int, year_end: int) -> str:
    payload = f"{normalize_title(topic)}|{','.join(sorted(normalize_title(item) for item in keywords))}|{year_start}|{year_end}"
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:16]


def stable_hash(value: str, length: int = 16) -> str:
    return hashlib.sha1(normalize_text(value).encode("utf-8")).hexdigest()[:length]


def slugify_filename(value: str, max_length: int = 100) -> str:
    normalized = NON_ALNUM_RE.sub("-", normalize_title(value)).strip("-")
    if not normalized:
        normalized = "paper"
    return normalized[:max_length]


def ensure_parent_directory(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def top_terms(texts: Iterable[str], limit: int = 10) -> list[str]:
    counts: dict[str, int] = {}
    for text in texts:
        for token in normalize_title(text).split():
            if len(token) < 4 or token in STOPWORDS:
                continue
            counts[token] = counts.get(token, 0) + 1
    ranked = sorted(counts.items(), key=lambda item: item[1], reverse=True)
    return [token for token, _ in ranked[:limit]]
