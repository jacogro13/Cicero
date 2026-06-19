"""In-memory ``DocumentExtractor`` double for unit tests — returns canned
Markdown without touching a real PDF library (ADR-009).
"""

from __future__ import annotations

from pagemaster.domain.document.ports.document_extractor import DocumentExtractor


class StubDocumentExtractor(DocumentExtractor):
    def __init__(self, markdown: str = "# Extracted\n") -> None:
        self._markdown = markdown

    async def extract_markdown(self, data: bytes) -> str:
        return self._markdown
