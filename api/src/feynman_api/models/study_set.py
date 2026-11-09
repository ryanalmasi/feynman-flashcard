import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from feynman_api.models.base import Base

if TYPE_CHECKING:
    from feynman_api.models.document import Document
    from feynman_api.models.flashcard import Flashcard


class StudySet(Base):
    __tablename__ = "study_sets"
    __table_args__ = (
        CheckConstraint("char_length(title) BETWEEN 1 AND 120", name="title_length"),
        CheckConstraint(
            "description IS NULL OR char_length(description) <= 1000", name="description_length"
        ),
        Index("ix_study_sets_user_id_created_at", "user_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(nullable=False)
    description: Mapped[str | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    flashcards: Mapped[list["Flashcard"]] = relationship(
        back_populates="study_set", cascade="all, delete-orphan", passive_deletes=True
    )
    document: Mapped["Document | None"] = relationship(
        back_populates="study_set",
        uselist=False,
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
