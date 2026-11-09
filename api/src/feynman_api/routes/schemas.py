import uuid
from datetime import datetime
from typing import Annotated, Literal, Self

from pydantic import AfterValidator, BaseModel, Field, StringConstraints, model_validator


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
