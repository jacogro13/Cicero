from abc import ABC, abstractmethod


class DocumentSummarizer(ABC):
    """Port: turn a document's extracted Markdown into its summary (ADR-016)."""

    @abstractmethod
    async def summarize(self, markdown: str) -> str:
        """Summarise the extracted Markdown into the reader-facing summary text."""
        ...
