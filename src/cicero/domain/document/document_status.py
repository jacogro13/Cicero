from enum import Enum


class DocumentStatus(str, Enum):
    """Lifecycle state of a document's extraction (ADR-002).

    Forward-only: ``UPLOADED → PROCESSING → READY | FAILED``. The extracted text
    (at ``Document.content_key``) exists when (and only when) the status is READY.
    """

    UPLOADED = "UPLOADED"
    PROCESSING = "PROCESSING"
    READY = "READY"
    FAILED = "FAILED"
