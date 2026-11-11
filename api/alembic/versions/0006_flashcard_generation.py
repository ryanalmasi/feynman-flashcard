"""flashcard generation columns

Revision ID: 0006_flashcard_generation
Revises: 0005_knowledge_maps
Create Date: 2026-11-11
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0006_flashcard_generation"
down_revision: str | None = "0005_knowledge_maps"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NEW_BACK = (
    "(kind = 'qa' AND char_length(back) BETWEEN 1 AND 2000) "
    "OR (kind = 'cloze' AND char_length(back) <= 2000)"
)
OLD_BACK = "char_length(back) BETWEEN 1 AND 2000"


def upgrade() -> None:
    op.add_column("flashcards", sa.Column("kind", sa.String(), server_default="qa", nullable=False))
    op.add_column(
        "flashcards", sa.Column("status", sa.String(), server_default="accepted", nullable=False)
    )
    op.add_column(
        "flashcards", sa.Column("edited", sa.Boolean(), server_default=sa.false(), nullable=False)
    )
    op.add_column("flashcards", sa.Column("concept_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        op.f("fk_flashcards_concept_id_concepts"),
        "flashcards",
        "concepts",
        ["concept_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_check_constraint(op.f("ck_flashcards_kind"), "flashcards", "kind IN ('qa','cloze')")
    op.create_check_constraint(
        op.f("ck_flashcards_status"), "flashcards", "status IN ('suggested','accepted')"
    )
    op.drop_constraint(op.f("ck_flashcards_back_length"), "flashcards", type_="check")
    op.create_check_constraint(op.f("ck_flashcards_back_length"), "flashcards", NEW_BACK)
    op.create_index(
        "ix_flashcards_study_set_id_status_created_at",
        "flashcards",
        ["study_set_id", "status", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_flashcards_study_set_id_status_created_at", table_name="flashcards")
    op.drop_constraint(op.f("ck_flashcards_back_length"), "flashcards", type_="check")
    op.create_check_constraint(op.f("ck_flashcards_back_length"), "flashcards", OLD_BACK)
    op.drop_constraint(op.f("ck_flashcards_status"), "flashcards", type_="check")
    op.drop_constraint(op.f("ck_flashcards_kind"), "flashcards", type_="check")
    op.drop_constraint(op.f("fk_flashcards_concept_id_concepts"), "flashcards", type_="foreignkey")
    op.drop_column("flashcards", "concept_id")
    op.drop_column("flashcards", "edited")
    op.drop_column("flashcards", "status")
    op.drop_column("flashcards", "kind")
