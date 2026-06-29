from abc import ABC, abstractmethod


class DocumentExtractor(ABC):
    """Port: turn a source file's bytes into Markdown (ADR-009).

    Reached from a use case, never constructed directly. The extracted text is
    internal raw material for summarization, never shown to the reader. PDF-only
    for now; URL ingest and chapter structure extend the port when they land.
    """

    @abstractmethod
    async def extract_markdown(self, data: bytes) -> str:
        """Extract a single Markdown string from PDF ``data``."""
        ...
