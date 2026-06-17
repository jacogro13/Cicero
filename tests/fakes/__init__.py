"""In-memory test doubles for the domain ports.

Split by adapter kind: persistence (repository + Unit of Work) and storage. The
storage double is imported from ``tests.fakes.storage`` directly until its port
lands (ADR-004); it is re-exported here once green.
"""

from tests.fakes.persistence import (
    InMemoryDocumentRepository,
    InMemoryUnitOfWork,
    make_in_memory_uow_factory,
)

__all__ = [
    "InMemoryDocumentRepository",
    "InMemoryUnitOfWork",
    "make_in_memory_uow_factory",
]
