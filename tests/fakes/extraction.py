"""In-memory ``DocumentExtractor`` double for unit tests — returns canned chapters
without touching a real PDF library (ADR-009/021).
"""

from __future__ import annotations

from cicero.domain.document.chapter import Chapter
from cicero.domain.document.ports.document_extractor import DocumentExtractor


class StubDocumentExtractor(DocumentExtractor):
    def __init__(self, chapters: list[Chapter] | None = None) -> None:
        self._chapters = chapters if chapters is not None else [Chapter("Chapter One", "# Extracted\n")]

    async def extract(self, data: bytes) -> list[Chapter]:
        return self._chapters
