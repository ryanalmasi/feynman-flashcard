import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from feynman_api.models.base import Base
from feynman_api.models.study_set import StudySet


class KnowledgeMap(Base):
    __tablename__ = "knowledge_maps"
    __table_args__ = (
        CheckConstraint("status IN ('processing','ready','failed')", name="status"),
        CheckConstraint("cards_status IN ('idle','processing','failed')", name="cards_status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    study_set_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("study_sets.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(nullable=False)
    error_message: Mapped[str | None] = mapped_column(nullable=True)
    model_id: Mapped[str | None] = mapped_column(nullable=True)
    revision: Mapped[int] = mapped_column(nullable=False, default=0, server_default="0")
    cards_status: Mapped[str] = mapped_column(nullable=False, default="idle", server_default="idle")
    cards_error_message: Mapped[str | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    study_set: Mapped["StudySet"] = relationship(back_populates="knowledge_map")
    concepts: Mapped[list["Concept"]] = relationship(
        back_populates="knowledge_map",
        order_by="Concept.position",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class Concept(Base):
    __tablename__ = "concepts"
    __table_args__ = (
        UniqueConstraint(
            "knowledge_map_id",
            "position",
            name="uq_concepts_map_position",
            deferrable=True,
            initially="DEFERRED",
        ),
        CheckConstraint("char_length(title) BETWEEN 1 AND 120", name="title_length"),
        CheckConstraint("char_length(explanation) BETWEEN 1 AND 2000", name="explanation_length"),
        CheckConstraint("importance IN ('core','supporting','detail')", name="importance"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    knowledge_map_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("knowledge_maps.id", ondelete="CASCADE"), nullable=False
    )
    position: Mapped[int] = mapped_column(nullable=False)
    title: Mapped[str] = mapped_column(nullable=False)
    explanation: Mapped[str] = mapped_column(nullable=False)
    importance: Mapped[str] = mapped_column(nullable=False)
    key_terms: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    misconceptions: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    source_pages: Mapped[list[int]] = mapped_column(
        ARRAY(Integer), nullable=False, default=list, server_default=text("'{}'::integer[]")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    knowledge_map: Mapped[KnowledgeMap] = relationship(back_populates="concepts")


class KnowledgeMapChunk(Base):
    __tablename__ = "knowledge_map_chunks"
    __table_args__ = (CheckConstraint("status IN ('pending','done')", name="status"),)

    knowledge_map_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("knowledge_maps.id", ondelete="CASCADE"), primary_key=True
    )
    chunk_index: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
    page_start: Mapped[int] = mapped_column(nullable=False)
    page_end: Mapped[int] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(nullable=False)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    usage: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
