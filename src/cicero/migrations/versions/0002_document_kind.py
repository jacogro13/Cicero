"""document kind — the first real ALTER (ADR-026)

Adds ``documents.kind`` (``BOOK``/``ARTICLE``), the first migration to alter an
existing table rather than create one — ADR-024's payoff. A ``server_default`` of
``BOOK`` backfills every existing row in the single ``ADD COLUMN`` statement.

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-26
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# create_type=False: created explicitly below so ADD COLUMN does not also emit
# CREATE TYPE.
document_kind = postgresql.ENUM("BOOK", "ARTICLE", name="document_kind", create_type=False)


def upgrade() -> None:
    document_kind.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "documents",
        sa.Column("kind", document_kind, nullable=False, server_default="BOOK"),
    )


def downgrade() -> None:
    op.drop_column("documents", "kind")
    document_kind.drop(op.get_bind(), checkfirst=True)
