"""In-memory test doubles for the domain ports.

Split by adapter kind: persistence (repository + Unit of Work) and storage.
"""

from tests.fakes.persistence import (
    InMemoryDocumentRepository,
    InMemoryUnitOfWork,
    make_in_memory_uow_factory,
)
from tests.fakes.storage import InMemoryDocumentStorage

__all__ = [
    "InMemoryDocumentRepository",
    "InMemoryUnitOfWork",
    "make_in_memory_uow_factory",
    "InMemoryDocumentStorage",
]
