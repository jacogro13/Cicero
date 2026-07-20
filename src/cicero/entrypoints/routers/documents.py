from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile

from cicero.domain.document import commands
from cicero.domain.document.document_id import DocumentId
from cicero.domain.ports.unit_of_work import UnitOfWorkFactory
from cicero.entrypoints.dependencies import get_message_bus, get_uow_factory
from cicero.entrypoints.schemas import DocumentResponse, SummaryResponse
from cicero.services import views
from cicero.services.messagebus import MessageBus

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("", response_model=DocumentResponse, status_code=201)
async def create_document(
    file: UploadFile,
    title: str = Form(...),
    bus: MessageBus = Depends(get_message_bus),
) -> DocumentResponse:
    command = commands.UploadDocument(title=title, content=await file.read())
    document = await bus.handle(command)
    return DocumentResponse.from_domain(document)


@router.get("", response_model=list[DocumentResponse])
async def list_documents(
    uow_factory: UnitOfWorkFactory = Depends(get_uow_factory),
) -> list[DocumentResponse]:
    documents = await views.list_documents(uow_factory)
    return [DocumentResponse.from_view(view) for view in documents]


@router.get("/{document_id}/summary", response_model=SummaryResponse)
async def get_document_summary(
    document_id: UUID,
    uow_factory: UnitOfWorkFactory = Depends(get_uow_factory),
) -> SummaryResponse:
    summary = await views.get_document_summary(uow_factory, DocumentId(document_id))
    if summary is None:
        raise HTTPException(status_code=404, detail="summary not found")
    return SummaryResponse.from_view(summary)


@router.delete("/{document_id}", status_code=204)
async def delete_document(
    document_id: UUID,
    bus: MessageBus = Depends(get_message_bus),
) -> None:
    await bus.handle(commands.DeleteDocument(document_id=DocumentId(document_id)))
