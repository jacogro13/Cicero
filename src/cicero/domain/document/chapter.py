from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Chapter:
    """A document chapter: its bookmark title and extracted Markdown (ADR-021)."""

    title: str
    markdown: str
