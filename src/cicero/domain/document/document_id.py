from __future__ import annotations

import uuid
from dataclasses import dataclass


@dataclass(frozen=True)
class DocumentId:
    """Identity of a document, backed by a UUID."""

    value: uuid.UUID

    @classmethod
    def new(cls) -> DocumentId:
        return cls(value=uuid.uuid4())
