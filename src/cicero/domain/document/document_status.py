from enum import Enum


class DocumentStatus(str, Enum):
    """Where a document sits in the processing pipeline (ADR-014, superseding ADR-002).

    Forward-only: ``UPLOADED → EXTRACTING → EXTRACTED | FAILED``. Each member names the
    stage reached, not readiness, so the edge can derive the *next* stage from it and a
    later stage appends to the chain rather than redefining a terminal name. The
    extracted text (at ``Document.content_key``) exists from ``EXTRACTED`` onwards.
    """

    UPLOADED = "UPLOADED"
    EXTRACTING = "EXTRACTING"
    EXTRACTED = "EXTRACTED"
    FAILED = "FAILED"
