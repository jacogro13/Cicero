from __future__ import annotations

from fastapi import Depends

from pagemaster.domain.document.ports.document_storage import DocumentStorage
from pagemaster.domain.ports.unit_of_work import UnitOfWorkFactory
from pagemaster.services.document.list_documents import ListDocuments
from pagemaster.services.document.upload_document import UploadDocument


def get_uow_factory() -> UnitOfWorkFactory:
    """Provide the Unit-of-Work factory. No persistence adapter is wired yet;
    tests override this via ``app.dependency_overrides`` until one lands (ADR-005)."""
    raise NotImplementedError("no persistence adapter wired yet")


def get_document_storage() -> DocumentStorage:
    """Provide object storage. No adapter is wired yet; tests override this via
    ``app.dependency_overrides`` until one lands (ADR-005)."""
    raise NotImplementedError("no storage adapter wired yet")


def get_upload_document(
    uow_factory: UnitOfWorkFactory = Depends(get_uow_factory),
    storage: DocumentStorage = Depends(get_document_storage),
) -> UploadDocument:
    return UploadDocument(uow_factory, storage)


def get_list_documents(
    uow_factory: UnitOfWorkFactory = Depends(get_uow_factory),
) -> ListDocuments:
    return ListDocuments(uow_factory)
