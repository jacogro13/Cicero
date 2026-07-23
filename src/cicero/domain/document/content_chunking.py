"""Pure chunker for splitting oversized content into budget-sized slices (ADR-020).

An input larger than the LLM's context is summarised via map-reduce: slice it
into chunks that each fit the char budget, summarise each, synthesise one summary
from the parts. This module is that slice — pure (no framework deps) and in the
domain layer so the retrieval-index stage can reuse it.
"""

from __future__ import annotations

import re

_FENCE_PATTERN = re.compile(r"^[ \t]*```")


def _paragraphs(markdown: str) -> list[str]:
    """Split Markdown into paragraph blocks, treating fenced code as atomic.

    A paragraph is a maximal run of non-blank lines between blank lines. Blank
    lines *inside* a fenced code block do not break it, so a fence is never split.
    """
    blocks: list[str] = []
    current: list[str] = []
    in_fence = False
    for line in markdown.split("\n"):
        if _FENCE_PATTERN.match(line):
            in_fence = not in_fence
            current.append(line)
            continue
        if in_fence:
            current.append(line)
            continue
        if line.strip() == "":
            if current:
                blocks.append("\n".join(current))
                current = []
        else:
            current.append(line)
    if current:
        blocks.append("\n".join(current))
    return blocks


def split_for_budget(markdown: str, max_chars: int) -> list[str]:
    """Ordered chunks of ``markdown``, each at most ``max_chars`` long.

    Chunks break at paragraph boundaries (greedily packed), keeping fenced code
    blocks intact. A single paragraph that alone exceeds ``max_chars`` — the last
    resort, e.g. one enormous fenced block — is hard-split on character count.
    Returns ``[]`` for empty input.
    """
    chunks: list[str] = []
    buf = ""
    for para in _paragraphs(markdown):
        if len(para) > max_chars:
            if buf:
                chunks.append(buf)
                buf = ""
            for i in range(0, len(para), max_chars):
                chunks.append(para[i : i + max_chars])
            continue
        candidate = f"{buf}\n\n{para}" if buf else para
        if len(candidate) <= max_chars:
            buf = candidate
        else:
            chunks.append(buf)
            buf = para
    if buf:
        chunks.append(buf)
    return chunks
