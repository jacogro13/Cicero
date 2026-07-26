from enum import Enum


class EnrichmentStatus(str, Enum):
    """Where a document sits on the enrichment branch (ADR-028).

    A separate axis from ``DocumentStatus``: enrichment (cover, authors, year) is
    best-effort and never gates readability, so it carries its own per-artifact
    status. ``PENDING → ENRICHING → ENRICHED``, or ``→ FAILED`` on any error.
    """

    PENDING = "PENDING"
    ENRICHING = "ENRICHING"
    ENRICHED = "ENRICHED"
    FAILED = "FAILED"
