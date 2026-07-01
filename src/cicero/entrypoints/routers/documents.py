from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Form, UploadFile

from cicero.domain.document import commands
from cicero.domain.document.document_id import DocumentId
from cicero.entrypoints.dependencies import get_message_bus
from cicero.entrypoints.schemas import DocumentResponse
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
    bus: MessageBus = Depends(get_message_bus),
) -> list[DocumentResponse]:
    documents = await bus.handle(commands.ListDocuments())
    return [DocumentResponse.from_domain(document) for document in documents]


@router.delete("/{document_id}", status_code=204)
async def delete_document(
    document_id: UUID,
    bus: MessageBus = Depends(get_message_bus),
) -> None:
    await bus.handle(commands.DeleteDocument(document_id=DocumentId(document_id)))
