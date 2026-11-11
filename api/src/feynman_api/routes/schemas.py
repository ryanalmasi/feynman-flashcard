import uuid
from datetime import datetime
from typing import Annotated, Literal, Self

from pydantic import AfterValidator, BaseModel, Field, StringConstraints, model_validator

from feynman_api.knowledge.limits import (
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
Back = Annotated[str, Field(min_length=1, max_length=2000), NoNul]


def _reject_blank(value: str | None) -> None:
    # Card text is stored unmodified; whitespace-only is rejected but never trimmed.
    if value is not None and value.strip() == "":
        raise ValueError("must not be blank")


class DocumentSummary(BaseModel):
    id: uuid.UUID
    status: Literal["processing", "ready", "failed"]
    page_count: int | None
    original_filename: str
    error_message: str | None


class StudySetOut(BaseModel):
    id: uuid.UUID
    title: str
    description: str | None
    card_count: int
    document: DocumentSummary | None
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
    created_at: datetime
    updated_at: datetime


class FlashcardCreate(BaseModel):
    front: Front
    back: Back

    @model_validator(mode="after")
    def _not_blank(self) -> Self:
        _reject_blank(self.front)
        _reject_blank(self.back)
        return self


class FlashcardUpdate(BaseModel):
    front: Front | None = None
    back: Back | None = None

    @model_validator(mode="after")
    def _valid(self) -> Self:
        for name in ("front", "back"):
            value = getattr(self, name)
            if name in self.model_fields_set and value is None:
                raise ValueError(f"{name} must not be null")
            _reject_blank(value)
        return self


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
