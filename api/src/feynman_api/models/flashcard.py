import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Uuid, false, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from feynman_api.models.base import Base
from feynman_api.models.study_set import StudySet


class Flashcard(Base):
    __tablename__ = "flashcards"
    __table_args__ = (
        CheckConstraint("char_length(front) BETWEEN 1 AND 500", name="front_length"),
        CheckConstraint(
            "(kind = 'qa' AND char_length(back) BETWEEN 1 AND 2000) "
            "OR (kind = 'cloze' AND char_length(back) <= 2000)",
            name="back_length",
        ),
        CheckConstraint("kind IN ('qa','cloze')", name="kind"),
        CheckConstraint("status IN ('suggested','accepted')", name="status"),
        CheckConstraint("origin IN ('manual','generated')", name="origin"),
        Index("ix_flashcards_study_set_id_created_at", "study_set_id", "created_at"),
        Index(
            "ix_flashcards_study_set_id_status_created_at", "study_set_id", "status", "created_at"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    study_set_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("study_sets.id", ondelete="CASCADE"), nullable=False
    )
    front: Mapped[str] = mapped_column(nullable=False)
    back: Mapped[str] = mapped_column(nullable=False)
    origin: Mapped[str] = mapped_column(nullable=False, default="manual", server_default="manual")
    concept_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("concepts.id", ondelete="SET NULL"), nullable=True
    )
    kind: Mapped[str] = mapped_column(nullable=False, default="qa", server_default="qa")
    status: Mapped[str] = mapped_column(
        nullable=False, default="accepted", server_default="accepted"
    )
    edited: Mapped[bool] = mapped_column(nullable=False, default=False, server_default=false())
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    study_set: Mapped[StudySet] = relationship(back_populates="flashcards")
