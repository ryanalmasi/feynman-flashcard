"""Validate and clamp raw LLM extraction output (pure)."""

from collections.abc import Iterable

from feynman_api.knowledge.limits import (
    EXPLANATION_MAX,
    KEY_TERMS_MAX,
    MISCONCEPTION_MAX,
    MISCONCEPTIONS_MAX,
    SOURCE_PAGES_MAX,
    SYNONYMS_MAX,
    TERM_MAX,
    TITLE_MAX,
)
from feynman_api.knowledge.schemas import ChunkExtraction, ConceptDraft


def clamp(value: str, limit: int) -> str:
    return value.replace("\x00", "").strip()[:limit].rstrip()


def normalise_ws(value: str) -> str:
    return " ".join(value.split())


def clean_synonyms(values: Iterable[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for raw in values:
        s = clamp(raw, TERM_MAX)
        if s and s.casefold() not in seen:
            seen.add(s.casefold())
            out.append(s)
    return out[:SYNONYMS_MAX]


def clean_misconceptions(values: Iterable[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for raw in values:
        s = normalise_ws(clamp(raw, MISCONCEPTION_MAX))
        if s and s not in seen:
            seen.add(s)
            out.append(s)
    return out[:MISCONCEPTIONS_MAX]


def clean_extraction(raw: ChunkExtraction, page_start: int, page_end: int) -> list[ConceptDraft]:
    drafts: list[ConceptDraft] = []
    for concept in raw.concepts:
        title = clamp(concept.title, TITLE_MAX)
        explanation = clamp(concept.explanation, EXPLANATION_MAX)
        if not title or not explanation:
            continue
        terms: dict[str, tuple[str, list[str]]] = {}
        for kt in concept.key_terms:
            term = clamp(kt.term, TERM_MAX)
            if not term:
                continue
            key = term.casefold()
            if key in terms:
                terms[key] = (terms[key][0], terms[key][1] + list(kt.synonyms))
            else:
                terms[key] = (term, list(kt.synonyms))
        key_terms = [
            {"term": term, "synonyms": clean_synonyms(syns)} for term, syns in terms.values()
        ][:KEY_TERMS_MAX]
        pages = sorted({p for p in concept.source_pages if page_start <= p <= page_end})
        drafts.append(
            ConceptDraft(
                title=title,
                explanation=explanation,
                importance=concept.importance,
                key_terms=key_terms,
                misconceptions=clean_misconceptions(concept.misconceptions),
                source_pages=pages[:SOURCE_PAGES_MAX],
            )
        )
    return drafts
