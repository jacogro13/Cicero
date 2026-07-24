"""POST/GET/DELETE /api/documents over HTTP (ADR-005, ADR-013).

The routes are driven with a bus wired over the in-memory fakes, swapped in at the
``get_message_bus`` seam, so the HTTP layer is verified without real adapters. The job
queue is left **unstarted**: an upload enqueues extraction but no worker drains it, so
documents stay UPLOADED — the queue/extraction path is covered in the unit suite.
"""

import asyncio
import uuid

from fastapi.testclient import TestClient

from cicero.domain.document.document import Document
from cicero.domain.document.document_status import DocumentStatus
from cicero.entrypoints.dependencies import (
    bootstrap,
    get_document_storage,
    get_message_bus,
    get_uow_factory,
)
from cicero.entrypoints.job_queue import JobQueue
from cicero.entrypoints.main import create_app

from tests.fakes import (
    InMemoryDocumentStorage,
    StubDocumentExtractor,
    StubDocumentSummarizer,
    make_in_memory_uow_factory,
)

_PDF = ("clean-code.pdf", b"%PDF-1.4 bytes", "application/pdf")


def _client() -> TestClient:
    app = create_app()
    uow_factory = make_in_memory_uow_factory()
    storage = InMemoryDocumentStorage()
    bus = bootstrap(
        uow_factory,
        storage,
        StubDocumentExtractor("# Clean Code"),
        StubDocumentSummarizer("A crisp summary."),
        JobQueue(),
    )
    # Writes ride the bus; reads bypass it (ADR-015). Both share one uow_factory
    # and one store so a posted document — and its stored blobs — are visible to
    # the read side (ADR-019).
    app.dependency_overrides[get_message_bus] = lambda: bus
    app.dependency_overrides[get_uow_factory] = lambda: uow_factory
    app.dependency_overrides[get_document_storage] = lambda: storage
    return TestClient(app)


class TestCreateDocument:
    def test_post_creates_a_document_and_returns_201(self):
        client = _client()

        response = client.post(
            "/api/documents", data={"title": "Clean Code"}, files={"file": _PDF}
        )

        assert response.status_code == 201
        body = response.json()
        assert body["title"] == "Clean Code"
        assert body["status"] == DocumentStatus.UPLOADED.value
        uuid.UUID(body["id"])  # a valid generated id crosses the wire

    def test_response_omits_internal_storage_keys(self):
        client = _client()

        response = client.post(
            "/api/documents", data={"title": "Clean Code"}, files={"file": _PDF}
        )

        body = response.json()
        assert "content_key" not in body
        assert "source_key" not in body


class TestListDocuments:
    def test_get_returns_empty_list_when_no_documents(self):
        client = _client()

        response = client.get("/api/documents")

        assert response.status_code == 200
        assert response.json() == []

    def test_posted_document_appears_in_the_list(self):
        client = _client()
        client.post(
            "/api/documents", data={"title": "Clean Code"}, files={"file": _PDF}
        )

        response = client.get("/api/documents")

        assert response.status_code == 200
        assert [doc["title"] for doc in response.json()] == ["Clean Code"]


class TestDeleteDocument:
    def test_delete_removes_the_document_and_returns_204(self):
        client = _client()
        created = client.post(
            "/api/documents", data={"title": "Clean Code"}, files={"file": _PDF}
        ).json()

        response = client.delete(f"/api/documents/{created['id']}")

        assert response.status_code == 204
        assert client.get("/api/documents").json() == []

    def test_delete_unknown_id_returns_404(self):
        client = _client()

        response = client.delete(f"/api/documents/{uuid.uuid4()}")

        assert response.status_code == 404


class TestDocumentSummary:
    def test_summary_is_404_until_the_document_is_summarised(self):
        # The queue is unstarted here, so a freshly posted document has no summary
        # yet — the read route reports 404 rather than an empty body (ADR-016).
        client = _client()
        created = client.post(
            "/api/documents", data={"title": "Clean Code"}, files={"file": _PDF}
        ).json()

        response = client.get(f"/api/documents/{created['id']}/summary")

        assert response.status_code == 404


def _seed_extracted(client: TestClient) -> Document:
    """Put an EXTRACTED document + one chapter into the client's shared read seams,
    without running the pipeline."""
    overrides = client.app.dependency_overrides
    uow_factory = overrides[get_uow_factory]()
    storage = overrides[get_document_storage]()

    async def seed() -> Document:
        document = Document.create("Clean Code")
        document.mark_extracting()
        document.mark_extracted()
        async with uow_factory() as uow:
            await uow.documents.save(document)
            await uow.chapters.save(document.id, ["Clean Code"])
            await uow.commit()
        await storage.put(document.chapter_key(0), b"Extracted.")
        return document

    return asyncio.run(seed())


class TestDocumentContent:
    def test_serves_the_extracted_markdown(self):
        client = _client()
        document = _seed_extracted(client)

        response = client.get(f"/api/documents/{document.id.value}/content")

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/markdown")
        assert response.text == "# Clean Code\n\nExtracted."

    def test_is_404_until_the_document_is_extracted(self):
        client = _client()
        created = client.post(
            "/api/documents", data={"title": "Clean Code"}, files={"file": _PDF}
        ).json()

        response = client.get(f"/api/documents/{created['id']}/content")

        assert response.status_code == 404

    def test_unknown_id_returns_404(self):
        client = _client()

        response = client.get(f"/api/documents/{uuid.uuid4()}/content")

        assert response.status_code == 404


class TestDocumentFile:
    def test_streams_the_original_pdf(self):
        # The upload handler stored the source blob; the file route streams it back.
        client = _client()
        created = client.post(
            "/api/documents", data={"title": "Clean Code"}, files={"file": _PDF}
        ).json()

        response = client.get(f"/api/documents/{created['id']}/file")

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"
        assert response.content == _PDF[1]

    def test_unknown_id_returns_404(self):
        client = _client()

        response = client.get(f"/api/documents/{uuid.uuid4()}/file")

        assert response.status_code == 404


class TestDomainErrorMapping:
    def test_empty_title_returns_422(self):
        client = _client()

        response = client.post(
            "/api/documents", data={"title": "   "}, files={"file": _PDF}
        )

        assert response.status_code == 422
