from enum import Enum


class DocumentKind(str, Enum):
    """What sort of work a document is, for library browsing only (ADR-026).

    A classification, not a processing switch: no pipeline stage branches on it.
    The default derives from the source at ingest — PDF uploads are ``BOOK``, URL
    ingests ``ARTICLE`` — and the reader shows the two in separate grids.
    """

    BOOK = "BOOK"
    ARTICLE = "ARTICLE"
