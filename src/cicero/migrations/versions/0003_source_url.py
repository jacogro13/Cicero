"""source_url — URL-document source (ADR-027)

Adds the nullable ``documents.source_url``: the link a URL document is extracted
from (NULL for uploads). The second real ``ALTER``, after ``0002``'s ``kind``.

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-26
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("source_url", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("documents", "source_url")
