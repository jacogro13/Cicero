from enum import Enum


class DocumentStatus(str, Enum):
    """Lifecycle state of a document's extraction (see ADR-002).

    Transitions (no reverse transitions):
        UPLOADED -> PROCESSING -> READY
        UPLOADED -> PROCESSING -> FAILED

    UPLOADED: The source (uploaded file or URL) has been received; extraction
        has not started.
    PROCESSING: Extraction is running.
    READY: Text has been extracted and stored, and ``content_key`` is set.
    FAILED: Extraction failed; no extracted text is available.
    """

    UPLOADED = "UPLOADED"
    PROCESSING = "PROCESSING"
    READY = "READY"
    FAILED = "FAILED"
