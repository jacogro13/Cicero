"""In-memory test doubles for the domain ports.

Split by adapter kind: persistence (repository + Unit of Work), storage, and
extraction.
"""

from tests.fakes.enrichment import (
    StubArticleCoverRenderer,
    StubCoverRenderer,
    StubMetadataInferer,
)
from tests.fakes.extraction import StubArticleExtractor, StubDocumentExtractor
from tests.fakes.persistence import (
    InMemoryChapterReadModel,
    InMemoryDocumentRepository,
    InMemorySummaryReadModel,
    InMemoryUnitOfWork,
    make_in_memory_uow_factory,
)
from tests.fakes.storage import InMemoryDocumentStorage
from tests.fakes.summarization import StubDocumentSummarizer

__all__ = [
    "InMemoryChapterReadModel",
    "InMemoryDocumentRepository",
    "InMemorySummaryReadModel",
    "InMemoryUnitOfWork",
    "make_in_memory_uow_factory",
    "InMemoryDocumentStorage",
    "StubArticleCoverRenderer",
    "StubArticleExtractor",
    "StubCoverRenderer",
    "StubDocumentExtractor",
    "StubDocumentSummarizer",
    "StubMetadataInferer",
]
