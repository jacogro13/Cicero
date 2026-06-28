from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Form, UploadFile

from pagemaster.domain.document import commands
from pagemaster.domain.document.document_id import DocumentId
from pagemaster.entrypoints.dependencies import (
    get_delete_document,
    get_list_documents,
    get_message_bus,
)
from pagemaster.entrypoints.schemas import DocumentResponse
from pagemaster.services.document.delete_document import DeleteDocument
from pagemaster.services.document.list_documents import ListDocuments
from pagemaster.services.messagebus import MessageBus

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
    use_case: ListDocuments = Depends(get_list_documents),
) -> list[DocumentResponse]:
    documents = await use_case.execute()
    return [DocumentResponse.from_domain(document) for document in documents]


@router.delete("/{document_id}", status_code=204)
async def delete_document(
    document_id: UUID,
    use_case: DeleteDocument = Depends(get_delete_document),
) -> None:
    await use_case.execute(DocumentId(document_id))
