"""`chapter_ranges` (ADR-021): the pure map from a PDF's table of contents to
ordered chapter page ranges. Level-1 bookmarks are chapter starts, front matter
before the first bookmark joins the first chapter, deeper levels are ignored, and a
document with no bookmarks is a single whole-document chapter.

Bookmark pages follow ``fitz.get_toc()`` (1-based); ranges are 0-based inclusive,
ready for ``to_markdown(doc, pages=…)``.
"""

from __future__ import annotations

from cicero.domain.document.chapterization import ChapterRange, chapter_ranges


def test_no_bookmarks_is_a_single_whole_document_chapter():
    # The fallback — also the shape a URL-extracted article always takes.
    assert chapter_ranges([], page_count=10) == [
        ChapterRange(title="", first_page=0, last_page=9)
    ]


def test_a_single_bookmark_spans_the_whole_document():
    assert chapter_ranges([(1, "Only", 1)], page_count=5) == [
        ChapterRange(title="Only", first_page=0, last_page=4)
    ]


def test_each_level_1_bookmark_starts_a_chapter():
    toc = [(1, "One", 1), (1, "Two", 4), (1, "Three", 8)]

    assert chapter_ranges(toc, page_count=10) == [
        ChapterRange(title="One", first_page=0, last_page=2),
        ChapterRange(title="Two", first_page=3, last_page=6),
        ChapterRange(title="Three", first_page=7, last_page=9),
    ]


def test_front_matter_before_the_first_bookmark_joins_the_first_chapter():
    # First bookmark on page 3 (1-based): pages 1–2 are front matter and belong to
    # the first chapter, which therefore starts at page index 0.
    toc = [(1, "One", 3), (1, "Two", 6)]

    assert chapter_ranges(toc, page_count=8) == [
        ChapterRange(title="One", first_page=0, last_page=4),
        ChapterRange(title="Two", first_page=5, last_page=7),
    ]


def test_sub_chapter_bookmarks_do_not_start_chapters():
    # Only level-1 entries define chapters; deeper levels fold into their chapter.
    toc = [
        (1, "One", 1),
        (2, "One dot one", 2),
        (3, "One dot one dot one", 2),
        (1, "Two", 5),
    ]

    assert chapter_ranges(toc, page_count=6) == [
        ChapterRange(title="One", first_page=0, last_page=3),
        ChapterRange(title="Two", first_page=4, last_page=5),
    ]
