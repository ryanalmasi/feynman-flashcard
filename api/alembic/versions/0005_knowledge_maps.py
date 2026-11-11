"""knowledge maps, concepts, chunk results

Revision ID: 0005_knowledge_maps
Revises: 0004_jobs
Create Date: 2026-11-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0005_knowledge_maps"
down_revision: str | None = "0004_jobs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _ts() -> list[sa.Column[object]]:
    return [
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    ]


def upgrade() -> None:
    op.create_table(
        "knowledge_maps",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("study_set_id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("error_message", sa.String(), nullable=True),
        sa.Column("model_id", sa.String(), nullable=True),
        sa.Column("revision", sa.Integer(), server_default="0", nullable=False),
        sa.Column("cards_status", sa.String(), server_default="idle", nullable=False),
        sa.Column("cards_error_message", sa.String(), nullable=True),
        *_ts(),
        sa.CheckConstraint(
            "status IN ('processing','ready','failed')", name=op.f("ck_knowledge_maps_status")
        ),
        sa.CheckConstraint(
            "cards_status IN ('idle','processing','failed')",
            name=op.f("ck_knowledge_maps_cards_status"),
        ),
        sa.ForeignKeyConstraint(
            ["study_set_id"],
            ["study_sets.id"],
            name=op.f("fk_knowledge_maps_study_set_id_study_sets"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            name=op.f("fk_knowledge_maps_document_id_documents"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_knowledge_maps")),
        sa.UniqueConstraint("study_set_id", name=op.f("uq_knowledge_maps_study_set_id")),
    )
    op.create_table(
        "concepts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("knowledge_map_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("explanation", sa.String(), nullable=False),
        sa.Column("importance", sa.String(), nullable=False),
        sa.Column(
            "key_terms", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False
        ),
        sa.Column(
            "misconceptions",
            postgresql.JSONB(),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "source_pages",
            postgresql.ARRAY(sa.Integer()),
            server_default=sa.text("'{}'::integer[]"),
            nullable=False,
        ),
        *_ts(),
        sa.CheckConstraint(
            "char_length(title) BETWEEN 1 AND 120", name=op.f("ck_concepts_title_length")
        ),
        sa.CheckConstraint(
            "char_length(explanation) BETWEEN 1 AND 2000",
            name=op.f("ck_concepts_explanation_length"),
        ),
        sa.CheckConstraint(
            "importance IN ('core','supporting','detail')", name=op.f("ck_concepts_importance")
        ),
        sa.ForeignKeyConstraint(
            ["knowledge_map_id"],
            ["knowledge_maps.id"],
            name=op.f("fk_concepts_knowledge_map_id_knowledge_maps"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_concepts")),
        sa.UniqueConstraint(
            "knowledge_map_id",
            "position",
            name="uq_concepts_map_position",
            deferrable=True,
            initially="DEFERRED",
        ),
    )
    op.create_table(
        "knowledge_map_chunks",
        sa.Column("knowledge_map_id", sa.Uuid(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("page_start", sa.Integer(), nullable=False),
        sa.Column("page_end", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("result", postgresql.JSONB(), nullable=True),
        sa.Column("usage", postgresql.JSONB(), nullable=True),
        *_ts(),
        sa.CheckConstraint(
            "status IN ('pending','done')", name=op.f("ck_knowledge_map_chunks_status")
        ),
        sa.ForeignKeyConstraint(
            ["knowledge_map_id"],
            ["knowledge_maps.id"],
            name=op.f("fk_knowledge_map_chunks_knowledge_map_id_knowledge_maps"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "knowledge_map_id", "chunk_index", name=op.f("pk_knowledge_map_chunks")
        ),
    )


def downgrade() -> None:
    op.drop_table("knowledge_map_chunks")
    op.drop_table("concepts")
    op.drop_table("knowledge_maps")
