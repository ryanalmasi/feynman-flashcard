"""LLM-facing schemas (no length or count limits; limits are applied in clean.py)."""

from typing import Any, Literal

from pydantic import BaseModel

Importance = Literal["core", "supporting", "detail"]


class ExtractedKeyTerm(BaseModel):
    term: str
    synonyms: list[str]


class ExtractedConcept(BaseModel):
    title: str
    explanation: str
    importance: Importance
    key_terms: list[ExtractedKeyTerm]
    misconceptions: list[str]
    source_pages: list[int]


class ChunkExtraction(BaseModel):
    concepts: list[ExtractedConcept]


class MergeGroup(BaseModel):
    keep: str
    merge: list[str]


class MergeGroups(BaseModel):
    groups: list[MergeGroup]


class GeneratedCard(BaseModel):
    kind: Literal["qa", "cloze"]
    front: str
    back: str


class ConceptCards(BaseModel):
    concept_id: str
    cards: list[GeneratedCard]


class CardBatch(BaseModel):
    concepts: list[ConceptCards]


class ConceptDraft(BaseModel):
    """The cleaned, internal shape stored in knowledge_map_chunks.result."""

    title: str
    explanation: str
    importance: Importance
    key_terms: list[dict[str, Any]]
    misconceptions: list[str]
    source_pages: list[int]
