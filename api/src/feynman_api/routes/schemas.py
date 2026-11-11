import uuid
from datetime import datetime
from typing import Annotated, Literal, Self

from pydantic import AfterValidator, BaseModel, Field, StringConstraints, model_validator
from pydantic_core import PydanticCustomError

from feynman_api.knowledge.cloze import cloze_error
from feynman_api.knowledge.limits import (
    BACK_MAX,
    CARD_IDS_MAX,
    CONCEPTS_MAX,
    EXPLANATION_MAX,
    KEY_TERMS_MAX,
    MISCONCEPTION_MAX,
    MISCONCEPTIONS_MAX,
    SOURCE_PAGES_MAX,
    SYNONYMS_MAX,
    TERM_MAX,
)


def _no_nul(value: str) -> str:
    # Postgres text cannot hold NUL; reject it as a validation error instead of a 500.
    if "\x00" in value:
        raise ValueError("must not contain NUL characters")
    return value


NoNul = AfterValidator(_no_nul)
Title = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120), NoNul
]
Description = Annotated[str, Field(max_length=1000), NoNul]
Front = Annotated[str, Field(min_length=1, max_length=500), NoNul]
Back = Annotated[str, Field(max_length=BACK_MAX), NoNul]  # may be empty for cloze cards only
CardKind = Literal["qa", "cloze"]
CardStatus = Literal["suggested", "accepted"]
QA_BACK_MSG = "Q/A cards need an answer on the back."
BLANK_MSG = "must not be blank"


def _reject_blank(value: str | None) -> None:
    # Card text is stored unmodified; whitespace-only is rejected but never trimmed.
    if value is not None and value.strip() == "":
        raise ValueError(BLANK_MSG)


def card_rule_error(kind: str, front: str, back: str) -> tuple[str, str] | None:
    """(field, message) for a card that breaks its kind's rules (design 7.3), else None.

    Used by FlashcardCreate and by PATCH on the merged row, so both give the same message.
    """
    if not front.strip():
        return "front", BLANK_MSG
    if kind == "cloze":
        message = cloze_error(front)
        return None if message is None else ("front", message)
    if not back.strip():
        return "back", QA_BACK_MSG
    return None


class DocumentSummary(BaseModel):
    id: uuid.UUID
    status: Literal["processing", "ready", "failed"]
    page_count: int | None
    original_filename: str
    error_message: str | None


class KnowledgeMapSummary(BaseModel):
    status: Literal["processing", "ready", "failed"]
    cards_status: Literal["idle", "processing", "failed"]


class StudySetOut(BaseModel):
    id: uuid.UUID
    title: str
    description: str | None
    card_count: int  # accepted cards only
    suggested_count: int
    document: DocumentSummary | None
    knowledge_map: KnowledgeMapSummary | None
    created_at: datetime
    updated_at: datetime


class StudySetCreate(BaseModel):
    title: Title
    description: Description | None = None


class StudySetUpdate(BaseModel):
    """An omitted field is unchanged; an explicit null description clears it."""

    title: Title | None = None
    description: Description | None = None

    @model_validator(mode="after")
    def _title_not_null(self) -> Self:
        if "title" in self.model_fields_set and self.title is None:
            raise ValueError("title must not be null")
        return self


class FlashcardOut(BaseModel):
    id: uuid.UUID
    study_set_id: uuid.UUID
    front: str
    back: str
    origin: Literal["manual", "generated"]
    kind: CardKind
    status: CardStatus
    edited: bool
    concept_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


class FlashcardCreate(BaseModel):
    kind: CardKind = "qa"
    front: Front
    back: Back = ""

    @model_validator(mode="after")
    def _valid(self) -> Self:
        error = card_rule_error(self.kind, self.front, self.back)
        if error is not None:
            # PydanticCustomError keeps the message as-is (no "Value error, " prefix).
            raise PydanticCustomError("cloze", error[1])
        return self


class FlashcardUpdate(BaseModel):
    """An omitted field is unchanged; an explicit null is a 422. The route validates the
    merged row (stored values plus this patch) with `card_rule_error`."""

    front: Front | None = None
    back: Back | None = None
    kind: CardKind | None = None
    status: Literal["accepted"] | None = None

    @model_validator(mode="after")
    def _valid(self) -> Self:
        for name in ("front", "back", "kind", "status"):
            if name in self.model_fields_set and getattr(self, name) is None:
                raise ValueError(f"{name} must not be null")
        _reject_blank(self.front)
        return self


class GenerateCardsRequest(BaseModel):
    concept_id: uuid.UUID | None = None


class CardIdsRequest(BaseModel):
    """null (or omitted) means every suggested card of the set."""

    card_ids: Annotated[list[uuid.UUID], Field(max_length=CARD_IDS_MAX)] | None = None


class AcceptOut(BaseModel):
    accepted: int


class RejectOut(BaseModel):
    rejected: int


class DocumentOut(BaseModel):
    id: uuid.UUID
    study_set_id: uuid.UUID
    status: Literal["processing", "ready", "failed"]
    page_count: int | None
    error_message: str | None
    original_filename: str


class UploadOut(BaseModel):
    study_set: StudySetOut
    document: DocumentOut


Importance = Literal["core", "supporting", "detail"]
Term = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=TERM_MAX), NoNul
]
Explanation = Annotated[str, Field(min_length=1, max_length=EXPLANATION_MAX), NoNul]
Misconception = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=MISCONCEPTION_MAX),
    NoNul,
]


def _sorted_unique(pages: list[int]) -> list[int]:
    return sorted(set(pages))


SourcePages = Annotated[
    list[Annotated[int, Field(ge=1)]],
    Field(max_length=SOURCE_PAGES_MAX),
    AfterValidator(_sorted_unique),
]


class KeyTerm(BaseModel):
    term: Term
    synonyms: Annotated[list[Term], Field(max_length=SYNONYMS_MAX)] = []


KeyTerms = Annotated[list[KeyTerm], Field(max_length=KEY_TERMS_MAX)]
Misconceptions = Annotated[list[Misconception], Field(max_length=MISCONCEPTIONS_MAX)]


class ConceptOut(BaseModel):
    id: uuid.UUID
    position: int
    title: str
    explanation: str
    importance: Importance
    key_terms: list[KeyTerm]
    misconceptions: list[str]
    source_pages: list[int]


class ConceptCreate(BaseModel):
    title: Title
    explanation: Explanation
    importance: Importance
    key_terms: KeyTerms = []
    misconceptions: Misconceptions = []
    source_pages: SourcePages = []

    @model_validator(mode="after")
    def _not_blank(self) -> Self:
        _reject_blank(self.explanation)
        return self


class ConceptUpdate(BaseModel):
    """An omitted field is unchanged; an explicit null is a 422."""

    title: Title | None = None
    explanation: Explanation | None = None
    importance: Importance | None = None
    key_terms: KeyTerms | None = None
    misconceptions: Misconceptions | None = None
    source_pages: SourcePages | None = None

    @model_validator(mode="after")
    def _valid(self) -> Self:
        for name in self.model_fields_set:
            if getattr(self, name) is None:
                raise ValueError(f"{name} must not be null")
        _reject_blank(self.explanation)
        return self


class KnowledgeMapOut(BaseModel):
    id: uuid.UUID
    status: Literal["processing", "ready", "failed"]
    error_message: str | None
    model_id: str | None
    revision: int
    cards_status: Literal["idle", "processing", "failed"]
    cards_error_message: str | None
    source_filename: str
    concepts: list[ConceptOut]


class ConceptOrder(BaseModel):
    concept_ids: Annotated[list[uuid.UUID], Field(max_length=CONCEPTS_MAX)]
