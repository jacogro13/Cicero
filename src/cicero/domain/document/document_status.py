from enum import Enum


class DocumentStatus(str, Enum):
    """Where a document sits in the processing pipeline (ADR-014/016, superseding ADR-002).

    Forward-only spine: ``UPLOADED → EXTRACTING → EXTRACTED → SUMMARISING →
    SUMMARISED``, with ``FAILED`` the single terminal any stage falls to. Each member
    names the stage reached, not readiness, so the edge derives the *next* stage from
    it and a later stage appends to the chain. The extracted text (at
    ``Document.content_key``) exists from ``EXTRACTED`` onwards; the summary (the read
    experience) from ``SUMMARISED``.
    """

    UPLOADED = "UPLOADED"
    EXTRACTING = "EXTRACTING"
    EXTRACTED = "EXTRACTED"
    SUMMARISING = "SUMMARISING"
    SUMMARISED = "SUMMARISED"
    FAILED = "FAILED"
