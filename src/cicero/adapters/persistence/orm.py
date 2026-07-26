"""SQLAlchemy imperative mapping for the Document aggregate, keeping the domain free
of ORM imports (ADR-001, ADR-006).
"""

from __future__ import annotations

import uuid

from sqlalchemy import Column, Enum, Integer, String, Table, Uuid
from sqlalchemy.orm import registry
from sqlalchemy.types import TypeDecorator

from cicero.domain.document.document import Document
from cicero.domain.document.document_id import DocumentId
from cicero.domain.document.document_kind import DocumentKind
from cicero.domain.document.document_status import DocumentStatus

mapper_registry = registry()
metadata = mapper_registry.metadata


class DocumentIdType(TypeDecorator):
    """Stores the ``DocumentId`` value object as a UUID column."""

    impl = Uuid
    cache_ok = True

    def process_bind_param(self, value: DocumentId | None, dialect) -> uuid.UUID | None:
        return value.value if value is not None else None

    def process_result_value(self, value: uuid.UUID | None, dialect) -> DocumentId | None:
        return DocumentId(value) if value is not None else None


documents = Table(
    "documents",
    metadata,
    Column("id", DocumentIdType, primary_key=True),
    Column("title", String, nullable=False),
    Column("status", Enum(DocumentStatus, name="document_status"), nullable=False),
    # Browsing classification only (ADR-026); server default backfills the ALTER
    # and lets a bare INSERT stay legal — the app always sends a value.
    Column(
        "kind",
        Enum(DocumentKind, name="document_kind"),
        nullable=False,
        server_default=DocumentKind.BOOK.value,
    ),
)

# The chapters read model (ADR-021): a document's ordered chapter titles — its
# table of contents. Content lives in object storage; only the titles are here.
chapters = Table(
    "chapters",
    metadata,
    Column("document_id", DocumentIdType, primary_key=True),
    Column("position", Integer, primary_key=True),
    Column("title", String, nullable=False),
)

# The summaries read model (ADR-016/021): a denormalized projection of a document's
# per-chapter summaries — a plain table reached via Core statements, not mapped.
summaries = Table(
    "summaries",
    metadata,
    Column("document_id", DocumentIdType, primary_key=True),
    Column("position", Integer, primary_key=True),
    Column("text", String, nullable=False),
)

_mappers_started = False


def start_mappers() -> None:
    """Map ``Document`` onto its table. Idempotent."""
    global _mappers_started
    if _mappers_started:
        return
    mapper_registry.map_imperatively(Document, documents)
    _mappers_started = True
