from dataclasses import dataclass

from cicero.domain.messages import Command


@dataclass(frozen=True)
class UploadDocument(Command):
    """Store a source file under a new document and persist its metadata (ADR-011)."""

    title: str
    content: bytes
