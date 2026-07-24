"""Pure map from a PDF's table of contents to ordered chapter page ranges (ADR-021).

Level-1 bookmarks are chapter starts; front matter before the first joins the first
chapter; no bookmarks means a single whole-document chapter (the article/fallback
shape). Framework-free and in the domain, kept distinct from the PyMuPDF rendering.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

# A ``fitz.get_toc()`` entry: (level, title, 1-based page).
TocEntry = tuple[int, str, int]


@dataclass(frozen=True)
class ChapterRange:
    """A chapter's title and its 0-based inclusive page span, ready for rendering."""

    title: str
    first_page: int
    last_page: int


def chapter_ranges(toc: Sequence[TocEntry], page_count: int) -> list[ChapterRange]:
    """Ordered chapter ranges over a ``page_count``-page document.

    Chapters start at level-1 bookmarks (deeper levels fold in). The first chapter
    starts at page 0 so front matter is never dropped; the last runs to the end.
    With no level-1 bookmarks the whole document is one untitled chapter.
    """
    chapters = [(title, page - 1) for level, title, page in toc if level == 1]
    if not chapters:
        return [ChapterRange(title="", first_page=0, last_page=page_count - 1)]

    ranges: list[ChapterRange] = []
    for index, (title, start) in enumerate(chapters):
        first_page = 0 if index == 0 else start
        is_last = index == len(chapters) - 1
        last_page = page_count - 1 if is_last else chapters[index + 1][1] - 1
        ranges.append(ChapterRange(title, first_page, max(first_page, last_page)))
    return ranges
