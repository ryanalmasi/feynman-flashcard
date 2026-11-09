import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from feynman_api.models.base import Base
from feynman_api.models.study_set import StudySet


class Flashcard(Base):
    __tablename__ = "flashcards"
    __table_args__ = (
        CheckConstraint("char_length(front) BETWEEN 1 AND 500", name="front_length"),
        CheckConstraint("char_length(back) BETWEEN 1 AND 2000", name="back_length"),
        CheckConstraint("origin IN ('manual','generated')", name="origin"),
        Index("ix_flashcards_study_set_id_created_at", "study_set_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    study_set_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("study_sets.id", ondelete="CASCADE"), nullable=False
    )
    front: Mapped[str] = mapped_column(nullable=False)
    back: Mapped[str] = mapped_column(nullable=False)
    origin: Mapped[str] = mapped_column(nullable=False, default="manual", server_default="manual")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    study_set: Mapped[StudySet] = relationship(back_populates="flashcards")
