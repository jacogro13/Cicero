"""In-memory ``DocumentExtractor`` double for unit tests — returns canned chapters
without touching a real PDF library (ADR-009/021).
"""

from __future__ import annotations

from cicero.domain.document.chapter import Chapter
from cicero.domain.document.ports.article_extractor import ArticleExtractor
from cicero.domain.document.ports.document_extractor import DocumentExtractor


class StubDocumentExtractor(DocumentExtractor):
    def __init__(self, chapters: list[Chapter] | None = None) -> None:
        self._chapters = chapters if chapters is not None else [Chapter("Chapter One", "# Extracted\n")]

    async def extract(self, data: bytes) -> list[Chapter]:
        return self._chapters


class StubArticleExtractor(ArticleExtractor):
    """Canned single-chapter article, without touching the network (ADR-027)."""

    def __init__(self, chapter: Chapter | None = None) -> None:
        self._chapter = chapter if chapter is not None else Chapter("An Article", "# An Article\n")

    async def extract(self, url: str) -> Chapter:
        return self._chapter
