from abc import ABC, abstractmethod


class DocumentExtractor(ABC):
    """Port: turn a source file's bytes into Markdown (ADR-009). PDF-only for now."""

    @abstractmethod
    async def extract_markdown(self, data: bytes) -> str:
        """Extract a single Markdown string from PDF ``data``."""
        ...
