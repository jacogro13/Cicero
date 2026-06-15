from __future__ import annotations

from dataclasses import dataclass

from pagemaster.domain.document.document_id import DocumentId


@dataclass
class Document:
    """A library document.

    Construct via :meth:`create` so the id is generated and the title is
    validated; do not instantiate directly.
    """

    id: DocumentId
    title: str

    @classmethod
    def create(cls, title: str) -> Document:
        if not title.strip():
            raise ValueError("title must not be empty")
        return cls(id=DocumentId.new(), title=title)
