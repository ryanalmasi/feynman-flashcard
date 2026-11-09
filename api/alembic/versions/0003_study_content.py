"""study sets, flashcards, documents, document pages

Revision ID: 0003_study_content
Revises: 0002_auth_sessions_rate_limits
Create Date: 2026-11-09
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0003_study_content"
down_revision: str | None = "0002_auth_sessions_rate_limits"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _ts(name: str) -> sa.Column[sa.DateTime]:
    return sa.Column(
        name, sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
    )


def upgrade() -> None:
    op.create_table(
        "study_sets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        _ts("created_at"),
        _ts("updated_at"),
        sa.CheckConstraint(
            "char_length(title) BETWEEN 1 AND 120", name=op.f("ck_study_sets_title_length")
        ),
        sa.CheckConstraint(
            "description IS NULL OR char_length(description) <= 1000",
            name=op.f("ck_study_sets_description_length"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_study_sets_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_study_sets")),
    )
    op.create_index("ix_study_sets_user_id_created_at", "study_sets", ["user_id", "created_at"])
    op.create_table(
        "flashcards",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("study_set_id", sa.Uuid(), nullable=False),
        sa.Column("front", sa.String(), nullable=False),
        sa.Column("back", sa.String(), nullable=False),
        sa.Column("origin", sa.String(), server_default="manual", nullable=False),
        _ts("created_at"),
        _ts("updated_at"),
        sa.CheckConstraint(
            "char_length(front) BETWEEN 1 AND 500", name=op.f("ck_flashcards_front_length")
        ),
        sa.CheckConstraint(
            "char_length(back) BETWEEN 1 AND 2000", name=op.f("ck_flashcards_back_length")
        ),
        sa.CheckConstraint("origin IN ('manual','generated')", name=op.f("ck_flashcards_origin")),
        sa.ForeignKeyConstraint(
            ["study_set_id"],
            ["study_sets.id"],
            name=op.f("fk_flashcards_study_set_id_study_sets"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_flashcards")),
    )
    op.create_index(
        "ix_flashcards_study_set_id_created_at", "flashcards", ["study_set_id", "created_at"]
    )
    op.create_table(
        "documents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("study_set_id", sa.Uuid(), nullable=False),
        sa.Column("storage_key", sa.String(), nullable=False),
        sa.Column("original_filename", sa.String(), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("error_message", sa.String(), nullable=True),
        _ts("created_at"),
        _ts("updated_at"),
        sa.CheckConstraint(
            "status IN ('processing','ready','failed')", name=op.f("ck_documents_status")
        ),
        sa.CheckConstraint(
            "char_length(original_filename) BETWEEN 1 AND 255",
            name=op.f("ck_documents_original_filename_length"),
        ),
        sa.ForeignKeyConstraint(
            ["study_set_id"],
            ["study_sets.id"],
            name=op.f("fk_documents_study_set_id_study_sets"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_documents")),
        sa.UniqueConstraint("study_set_id", name=op.f("uq_documents_study_set_id")),
        sa.UniqueConstraint("storage_key", name=op.f("uq_documents_storage_key")),
    )
    op.create_table(
        "document_pages",
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("text", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            name=op.f("fk_document_pages_document_id_documents"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("document_id", "page_number", name=op.f("pk_document_pages")),
    )


def downgrade() -> None:
    op.drop_table("document_pages")
    op.drop_table("documents")
    op.drop_index("ix_flashcards_study_set_id_created_at", table_name="flashcards")
    op.drop_table("flashcards")
    op.drop_index("ix_study_sets_user_id_created_at", table_name="study_sets")
    op.drop_table("study_sets")
