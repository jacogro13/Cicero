from __future__ import annotations

import uuid

from pydantic import BaseModel

from cicero.domain.document.document import Document
from cicero.domain.document.document_status import DocumentStatus
from cicero.services.views import DocumentView


class DocumentResponse(BaseModel):
    """Wire shape of a document (ADR-005): identity, title, status only. Storage
    keys and the internal extracted text never cross the API boundary."""

    id: uuid.UUID
    title: str
    status: DocumentStatus

    @classmethod
    def from_domain(cls, document: Document) -> DocumentResponse:
        """From the write model — a create/upload echoes the affected aggregate."""
        return cls(id=document.id.value, title=document.title, status=document.status)

    @classmethod
    def from_view(cls, view: DocumentView) -> DocumentResponse:
        """From the read side (ADR-015) — the list endpoint renders read DTOs."""
        return cls(id=view.id.value, title=view.title, status=view.status)
