"""baseline — the current schema (ADR-024)

The honest baseline: ``documents``, ``chapters``, ``summaries`` (composite
``(document_id, position)`` key from ADR-021), and the ``document_status`` enum,
mirroring ``orm.py`` as of this migration. Not split to re-enact ADR-021 — that
reshape already shipped in the models and there is no history to preserve.

Revision ID: 0001
Revises:
Create Date: 2026-07-26
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# create_type=False: the type is created explicitly below so table creation does
# not also try to emit CREATE TYPE.
document_status = postgresql.ENUM(
    "UPLOADED",
    "EXTRACTING",
    "EXTRACTED",
    "SUMMARISING",
    "SUMMARISED",
    "FAILED",
    name="document_status",
    create_type=False,
)


def upgrade() -> None:
    document_status.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "documents",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("status", document_status, nullable=False),
    )
    op.create_table(
        "chapters",
        sa.Column("document_id", sa.Uuid(), primary_key=True),
        sa.Column("position", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(), nullable=False),
    )
    op.create_table(
        "summaries",
        sa.Column("document_id", sa.Uuid(), primary_key=True),
        sa.Column("position", sa.Integer(), primary_key=True),
        sa.Column("text", sa.String(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("summaries")
    op.drop_table("chapters")
    op.drop_table("documents")
    document_status.drop(op.get_bind(), checkfirst=True)
