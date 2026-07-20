from abc import ABC, abstractmethod


class DocumentSummarizer(ABC):
    """Port: turn a document's extracted Markdown into its summary (ADR-016).

    Reached from the summarisation use case, never constructed directly. One summary
    per document for now; per-chapter summaries extend the port when chapters land.
    """

    @abstractmethod
    async def summarize(self, markdown: str) -> str:
        """Summarise the extracted Markdown into the reader-facing summary text."""
        ...
