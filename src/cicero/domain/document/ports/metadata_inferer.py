from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class InferredMetadata:
    """Author(s) and year inferred from a document's opening text — either field
    ``None`` when the text does not reveal it (ADR-028)."""

    authors: str | None = None
    year: int | None = None


class MetadataInferer(ABC):
    """Port: infer author(s) and year from a document's opening text (ADR-028)."""

    @abstractmethod
    async def infer(self, text: str) -> InferredMetadata: ...
