"""enrichment — cover, authors, year (ADR-028)

Adds the enrichment branch's columns to ``documents``: ``enrichment_status``
(its own per-artifact axis, server-default ``PENDING`` so the ALTER backfills
existing rows), and the metadata ``authors``/``year``/``has_cover`` fill-columns.

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-26
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# create_type=False: created explicitly below so ADD COLUMN does not also emit
# CREATE TYPE.
enrichment_status = postgresql.ENUM(
    "PENDING", "ENRICHING", "ENRICHED", "FAILED",
    name="enrichment_status",
    create_type=False,
)


def upgrade() -> None:
    enrichment_status.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "documents",
        sa.Column(
            "enrichment_status",
            enrichment_status,
            nullable=False,
            server_default="PENDING",
        ),
    )
    op.add_column("documents", sa.Column("authors", sa.String(), nullable=True))
    op.add_column("documents", sa.Column("year", sa.Integer(), nullable=True))
    op.add_column(
        "documents",
        sa.Column("has_cover", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("documents", "has_cover")
    op.drop_column("documents", "year")
    op.drop_column("documents", "authors")
    op.drop_column("documents", "enrichment_status")
    enrichment_status.drop(op.get_bind(), checkfirst=True)
