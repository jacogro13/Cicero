from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class InferredMetadata:
    """Browsing metadata read from a document's opening text (ADR-028).

    Either field is ``None`` when the text does not reveal it; for a PDF the
    ``CoverRenderer``'s docinfo fills whatever is left blank.
    """

    authors: str | None = None
    year: int | None = None


class MetadataInferer(ABC):
    """Port: infer author(s) and year from a document's opening text (ADR-028).

    Config-selected like the summarizer: ``MockMetadataInferer`` is the zero-config
    default, an OpenAI-compatible adapter replaces it when ``LLM_BASE_URL`` is set.
    """

    @abstractmethod
    async def infer(self, text: str) -> InferredMetadata:
        """Infer metadata from the opening text; both fields may be ``None``."""
        ...
