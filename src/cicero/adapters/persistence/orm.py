"""SQLAlchemy mapping for the Document aggregate (ADR-006).

Imperative mapping keeps the domain free of ORM imports (ADR-001): the table and
the value-object ↔ column translations live here, and ``start_mappers`` wires them
onto the plain ``Document`` class. A fetch returns a real ``Document``.
"""

from __future__ import annotations

import uuid

from sqlalchemy import Column, Enum, String, Table, Uuid
from sqlalchemy.orm import registry
from sqlalchemy.types import TypeDecorator

from cicero.domain.document.document import Document
from cicero.domain.document.document_id import DocumentId
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
)

_mappers_started = False


def start_mappers() -> None:
    """Map ``Document`` onto its table (imperative mapping). Idempotent, so the
    composition root may call it once at startup and tests once per fixture."""
    global _mappers_started
    if _mappers_started:
        return
    mapper_registry.map_imperatively(Document, documents)
    _mappers_started = True
