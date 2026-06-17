from enum import Enum


class DocumentStatus(str, Enum):
    """Lifecycle state of a document's extraction (ADR-002).

    Forward-only: ``UPLOADED → PROCESSING → READY | FAILED``. ``content_key`` is
    set when (and only when) the document reaches READY.
    """

    UPLOADED = "UPLOADED"
    PROCESSING = "PROCESSING"
    READY = "READY"
    FAILED = "FAILED"
