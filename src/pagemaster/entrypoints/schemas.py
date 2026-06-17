from __future__ import annotations

import uuid

from pydantic import BaseModel

from pagemaster.domain.document.document import Document
from pagemaster.domain.document.document_status import DocumentStatus


class DocumentResponse(BaseModel):
    """Wire shape of a document (ADR-005): identity, title, status only. Storage
    keys and the internal extracted text never cross the API boundary."""

    id: uuid.UUID
    title: str
    status: DocumentStatus

    @classmethod
    def from_domain(cls, document: Document) -> DocumentResponse:
        return cls(id=document.id.value, title=document.title, status=document.status)
