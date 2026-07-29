from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Form, HTTPException, Response, UploadFile

from cicero.domain.document import commands
from cicero.domain.document.document_id import DocumentId
from cicero.domain.document.document_kind import DocumentKind
from cicero.domain.document.ports.document_storage import DocumentStorage
from cicero.domain.ports.unit_of_work import UnitOfWorkFactory
from cicero.entrypoints.dependencies import (
    get_document_storage,
    get_message_bus,
    get_uow_factory,
)
from cicero.entrypoints.schemas import (
    ChapterResponse,
    DocumentResponse,
    IngestUrlRequest,
    SummaryResponse,
    UpdateDocumentRequest,
)
from cicero.services import views
from cicero.services.messagebus import MessageBus

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("", response_model=DocumentResponse, status_code=201)
async def create_document(
    file: UploadFile,
    title: str = Form(...),
    kind: DocumentKind | None = Form(None),
    bus: MessageBus = Depends(get_message_bus),
) -> DocumentResponse:
    command = commands.UploadDocument(
        title=title, content=await file.read(), kind=kind
    )
    document = await bus.handle(command)
    return DocumentResponse.from_domain(document)


@router.post("/url", response_model=DocumentResponse, status_code=201)
async def ingest_url(
    body: IngestUrlRequest,
    bus: MessageBus = Depends(get_message_bus),
) -> DocumentResponse:
    """Ingest a web article by URL — no file, the link is the source (ADR-027)."""
    document = await bus.handle(commands.IngestUrl(url=body.url, kind=body.kind))
    return DocumentResponse.from_domain(document)


@router.patch("/{document_id}", response_model=DocumentResponse)
async def update_document(
    document_id: UUID,
    body: UpdateDocumentRequest,
    bus: MessageBus = Depends(get_message_bus),
) -> DocumentResponse:
    """Correct a document's browsing kind (ADR-026)."""
    document = await bus.handle(
        commands.SetDocumentKind(document_id=DocumentId(document_id), kind=body.kind)
    )
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


@router.get("/{document_id}/chapters", response_model=list[ChapterResponse])
async def get_document_chapters(
    document_id: UUID,
    uow_factory: UnitOfWorkFactory = Depends(get_uow_factory),
) -> list[ChapterResponse]:
    """The reader's table of contents with per-chapter summaries (ADR-021)."""
    chapters = await views.get_document_chapters(uow_factory, DocumentId(document_id))
    return [ChapterResponse.from_view(chapter) for chapter in chapters]


@router.get("/{document_id}/content")
async def get_document_content(
    document_id: UUID,
    uow_factory: UnitOfWorkFactory = Depends(get_uow_factory),
    storage: DocumentStorage = Depends(get_document_storage),
) -> Response:
    """Admin inspection: the extracted Markdown, 404 until EXTRACTED (ADR-019)."""
    markdown = await views.get_document_content(
        uow_factory, storage, DocumentId(document_id)
    )
    if markdown is None:
        raise HTTPException(status_code=404, detail="content not available")
    return Response(content=markdown, media_type="text/markdown")


@router.get("/{document_id}/file")
async def get_document_file(
    document_id: UUID,
    uow_factory: UnitOfWorkFactory = Depends(get_uow_factory),
    storage: DocumentStorage = Depends(get_document_storage),
) -> Response:
    """Admin inspection: the original PDF, 404 for a URL document with no source (ADR-019/027)."""
    content = await views.get_document_file(
        uow_factory, storage, DocumentId(document_id)
    )
    if content is None:
        raise HTTPException(status_code=404, detail="file not available")
    return Response(content=content, media_type="application/pdf")


# Cover bytes come from a PDF render (PNG) or an article's og:image (any format), so
# the content type is read off the magic bytes rather than assumed (ADR-028).
_IMAGE_SIGNATURES: tuple[tuple[bytes, str], ...] = (
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"GIF87a", "image/gif"),
    (b"GIF89a", "image/gif"),
)


def _image_media_type(data: bytes) -> str:
    """Sniff an image's media type from its leading bytes, or fall back to a generic
    binary type — the browser sniffs an ``<img>`` source regardless."""
    for signature, media_type in _IMAGE_SIGNATURES:
        if data.startswith(signature):
            return media_type
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return "application/octet-stream"


@router.get("/{document_id}/cover")
async def get_document_cover(
    document_id: UUID,
    uow_factory: UnitOfWorkFactory = Depends(get_uow_factory),
    storage: DocumentStorage = Depends(get_document_storage),
) -> Response:
    """The document's cover image, 404 until enrichment has rendered one (ADR-028)."""
    cover = await views.get_document_cover(
        uow_factory, storage, DocumentId(document_id)
    )
    if cover is None:
        raise HTTPException(status_code=404, detail="cover not available")
    return Response(content=cover, media_type=_image_media_type(cover))


@router.delete("/{document_id}", status_code=204)
async def delete_document(
    document_id: UUID,
    bus: MessageBus = Depends(get_message_bus),
) -> None:
    await bus.handle(commands.DeleteDocument(document_id=DocumentId(document_id)))
