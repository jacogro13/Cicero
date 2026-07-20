"""In-memory ``DocumentSummarizer`` double for unit tests — returns canned summary
text and records what it was handed, without calling a real LLM (ADR-016).
"""

from __future__ import annotations

from cicero.domain.document.ports.document_summarizer import DocumentSummarizer


class StubDocumentSummarizer(DocumentSummarizer):
    def __init__(self, summary: str = "A summary.") -> None:
        self._summary = summary
        self.received: str | None = None

    async def summarize(self, markdown: str) -> str:
        self.received = markdown
        return self._summary
