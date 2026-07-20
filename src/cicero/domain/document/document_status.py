from enum import Enum


class DocumentStatus(str, Enum):
    """Where a document sits in the pipeline (ADR-014/016, superseding ADR-002).

    Forward-only ``UPLOADED → EXTRACTING → EXTRACTED → SUMMARISING → SUMMARISED``,
    with ``FAILED`` the single terminal. Each member names the stage reached.
    """

    UPLOADED = "UPLOADED"
    EXTRACTING = "EXTRACTING"
    EXTRACTED = "EXTRACTED"
    SUMMARISING = "SUMMARISING"
    SUMMARISED = "SUMMARISED"
    FAILED = "FAILED"
