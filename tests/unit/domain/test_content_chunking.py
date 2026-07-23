"""`split_for_budget` (ADR-020): the pure chunker behind map-reduce
summarization — greedy paragraph packing under a char budget, fenced code kept
atomic, an over-budget paragraph hard-split as the last resort.
"""

from __future__ import annotations

from cicero.domain.document.content_chunking import split_for_budget


def test_empty_input_yields_no_chunks():
    assert split_for_budget("", 100) == []


def test_a_single_small_paragraph_is_one_chunk():
    assert split_for_budget("Just one paragraph.", 100) == ["Just one paragraph."]


def test_paragraphs_are_packed_greedily_under_the_budget():
    markdown = "aaaa\n\nbbbb\n\ncccc"  # three 4-char paragraphs

    # 10 chars fits "aaaa\n\nbbbb" (10) but not a third paragraph.
    assert split_for_budget(markdown, 10) == ["aaaa\n\nbbbb", "cccc"]


def test_each_chunk_stays_within_the_budget():
    markdown = "\n\n".join(f"paragraph number {i}" for i in range(20))

    for chunk in split_for_budget(markdown, 50):
        assert len(chunk) <= 50


def test_a_fenced_code_block_is_never_split_at_its_blank_lines():
    markdown = "```\nline 1\n\nline 2\n```"  # a blank line lives inside the fence

    # The whole fence is one paragraph, so a budget large enough for it keeps it whole.
    assert split_for_budget(markdown, 100) == [markdown]


def test_a_paragraph_larger_than_the_budget_is_hard_split():
    chunks = split_for_budget("x" * 25, 10)

    assert chunks == ["x" * 10, "x" * 10, "x" * 5]
