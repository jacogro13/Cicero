from abc import ABC, abstractmethod

from cicero.domain.document.chapter import Chapter


class DocumentExtractor(ABC):
    """Port: turn a source file's bytes into ordered chapters (ADR-009/021). PDF-only for now."""

    @abstractmethod
    async def extract(self, data: bytes) -> list[Chapter]:
        """Extract ordered chapters from PDF ``data`` — one per level-1 bookmark,
        or a single chapter when it has no table of contents."""
        ...
