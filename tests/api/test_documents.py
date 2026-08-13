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
from cicero.domain.exceptions import DomainError
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
    StubArticleCoverRenderer,
    StubArticleExtractor,
    StubCoverRenderer,
    StubDocumentExtractor,
    StubDocumentSummarizer,
    StubMetadataInferer,
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
        StubArticleExtractor(),
        StubDocumentSummarizer("A crisp summary."),
        StubCoverRenderer(),
        StubArticleCoverRenderer(),
        StubMetadataInferer(),
        JobQueue(),
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
        assert body["kind"] == "BOOK"  # a PDF upload defaults to BOOK (ADR-026)
        uuid.UUID(body["id"])  # a valid generated id crosses the wire

    def test_kind_can_be_overridden_on_upload(self):
        client = _client()

        response = client.post(
            "/api/documents",
            data={"title": "A Paper", "kind": "ARTICLE"},
            files={"file": _PDF},
        )

        assert response.json()["kind"] == "ARTICLE"

    def test_response_omits_internal_storage_keys(self):
        client = _client()

        response = client.post(
            "/api/documents", data={"title": "Clean Code"}, files={"file": _PDF}
        )

        body = response.json()
        assert "content_key" not in body
        assert "source_key" not in body


class TestIngestUrl:
    def test_post_url_creates_an_article_and_returns_201(self):
        client = _client()

        response = client.post(
            "/api/documents/url",
            json={"url": "https://example.com/blog/clean-architecture"},
        )

        assert response.status_code == 201
        body = response.json()
        assert body["kind"] == "ARTICLE"
        assert body["status"] == DocumentStatus.UPLOADED.value
        assert body["source_url"] == "https://example.com/blog/clean-architecture"
        uuid.UUID(body["id"])

    def test_an_ingested_url_appears_in_the_list(self):
        client = _client()
        client.post("/api/documents/url", json={"url": "https://example.com/a"})

        listed = client.get("/api/documents").json()
        assert [d["kind"] for d in listed] == ["ARTICLE"]

    def test_kind_can_be_overridden_on_ingest(self):
        client = _client()

        response = client.post(
            "/api/documents/url", json={"url": "https://example.com/a", "kind": "BOOK"}
        )

        assert response.json()["kind"] == "BOOK"

    def test_an_invalid_url_returns_422(self):
        client = _client()

        response = client.post("/api/documents/url", json={"url": "ftp://example.com/x"})

        assert response.status_code == 422


class TestUpdateDocumentKind:
    def test_patch_corrects_the_kind(self):
        client = _client()
        created = client.post(
            "/api/documents", data={"title": "Clean Code"}, files={"file": _PDF}
        ).json()

        response = client.patch(
            f"/api/documents/{created['id']}", json={"kind": "ARTICLE"}
        )

        assert response.status_code == 200
        assert response.json()["kind"] == "ARTICLE"
        # and the correction is visible on the read side
        listed = client.get("/api/documents").json()
        assert [d["kind"] for d in listed] == ["ARTICLE"]

    def test_patch_unknown_id_returns_404(self):
        client = _client()

        response = client.patch(
            f"/api/documents/{uuid.uuid4()}", json={"kind": "ARTICLE"}
        )

        assert response.status_code == 404


def _seed_failed(client: TestClient) -> Document:
    """Put a FAILED document into the client's shared read seam — the state a stage
    lands in when its upstream stays down (ADR-029/030)."""
    uow_factory = client.app.dependency_overrides[get_uow_factory]()

    async def seed() -> Document:
        document = Document.create("Clean Code")
        document.mark_extracting()
        document.mark_failed()
        async with uow_factory() as uow:
            await uow.documents.save(document)
            await uow.commit()
        return document

    return asyncio.run(seed())


class TestRetryDocument:
    def test_retry_accepts_a_failed_document_and_returns_it_to_uploaded(self):
        client = _client()
        document = _seed_failed(client)

        response = client.post(f"/api/documents/{document.id.value}/retry")

        assert response.status_code == 202
        assert response.json()["status"] == DocumentStatus.UPLOADED.value
        listed = client.get("/api/documents").json()
        assert [d["status"] for d in listed] == [DocumentStatus.UPLOADED.value]

    def test_retrying_a_document_that_did_not_fail_returns_409(self):
        # Well-formed request, wrong state — a conflict, not a validation error.
        client = _client()
        created = client.post(
            "/api/documents", data={"title": "Clean Code"}, files={"file": _PDF}
        ).json()

        response = client.post(f"/api/documents/{created['id']}/retry")

        assert response.status_code == 409

    def test_retry_unknown_id_returns_404(self):
        client = _client()

        response = client.post(f"/api/documents/{uuid.uuid4()}/retry")

        assert response.status_code == 404


def _seed_summarised(client: TestClient) -> Document:
    """A SUMMARISED document with a summary per chapter — the state an operator asks to
    have redone after changing the model or the prompt (ADR-032)."""
    uow_factory = client.app.dependency_overrides[get_uow_factory]()

    async def seed() -> Document:
        document = Document.create("Clean Code")
        document.mark_extracted()
        document.mark_summarised()
        async with uow_factory() as uow:
            await uow.documents.save(document)
            await uow.chapters.save(document.id, ["Intro"])
            await uow.summaries.save(document.id, 0, "The old summary.")
            await uow.commit()
        return document

    return asyncio.run(seed())


class TestResummariseDocument:
    def test_resummarise_sends_a_summarised_document_back_to_extracted(self):
        client = _client()
        document = _seed_summarised(client)

        response = client.post(f"/api/documents/{document.id.value}/resummarise")

        assert response.status_code == 202
        assert response.json()["status"] == DocumentStatus.EXTRACTED.value
        # The summary is gone from the read side, not merely queued for replacement.
        assert client.get(f"/api/documents/{document.id.value}/summary").status_code == 404

    def test_resummarising_a_document_that_is_not_summarised_returns_409(self):
        client = _client()
        created = client.post(
            "/api/documents", data={"title": "Clean Code"}, files={"file": _PDF}
        ).json()

        response = client.post(f"/api/documents/{created['id']}/resummarise")

        assert response.status_code == 409

    def test_resummarise_unknown_id_returns_404(self):
        client = _client()

        response = client.post(f"/api/documents/{uuid.uuid4()}/resummarise")

        assert response.status_code == 404


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

    def test_list_carries_the_enrichment_metadata(self):
        # The shelf reads authors/year/has_cover off the list DTO (ADR-028); a fresh
        # upload carries their un-enriched defaults rather than omitting the keys.
        client = _client()
        client.post(
            "/api/documents", data={"title": "Clean Code"}, files={"file": _PDF}
        )

        [doc] = client.get("/api/documents").json()

        assert doc["authors"] is None
        assert doc["year"] is None
        assert doc["has_cover"] is False


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

    def test_unknown_id_returns_404(self):
        # Same status as "not summarised yet", but the two must not be the same
        # answer: an absent document is DocumentNotFound (ADR-008), not an absent
        # summary.
        client = _client()

        response = client.get(f"/api/documents/{uuid.uuid4()}/summary")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"]
        assert "summary" not in response.json()["detail"]


def _seed_summarised(client: TestClient) -> Document:
    """Put a SUMMARISED document — chapter titles + per-chapter summaries — into the
    client's shared read seam, without running the pipeline."""
    uow_factory = client.app.dependency_overrides[get_uow_factory]()

    async def seed() -> Document:
        document = Document.create("Clean Code")
        document.mark_extracting()
        document.mark_extracted()
        document.mark_summarising()
        document.mark_summarised()
        async with uow_factory() as uow:
            await uow.documents.save(document)
            await uow.chapters.save(document.id, ["Intro", "Body"])
            await uow.summaries.save(document.id, 0, "First.")
            await uow.summaries.save(document.id, 1, "Second.")
            await uow.commit()
        return document

    return asyncio.run(seed())


class TestDocumentChapters:
    def test_serves_the_table_of_contents_with_summaries(self):
        client = _client()
        document = _seed_summarised(client)

        response = client.get(f"/api/documents/{document.id.value}/chapters")

        assert response.status_code == 200
        assert response.json() == [
            {"index": 0, "title": "Intro", "summary": "First."},
            {"index": 1, "title": "Body", "summary": "Second."},
        ]

    def test_unknown_id_returns_404(self):
        # Chapters are projections, so an unknown id reads as "no rows" unless the
        # view checks the document exists — otherwise a nonexistent document is
        # indistinguishable from an unextracted one (ADR-008).
        client = _client()

        response = client.get(f"/api/documents/{uuid.uuid4()}/chapters")

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

    def test_url_document_returns_404(self):
        # A URL article has no source blob (ADR-027); the file route reports a clean
        # 404 rather than failing on a missing key.
        client = _client()
        created = client.post(
            "/api/documents/url", json={"url": "https://example.com/blog/post"}
        ).json()

        response = client.get(f"/api/documents/{created['id']}/file")

        assert response.status_code == 404

    def test_unknown_id_returns_404(self):
        client = _client()

        response = client.get(f"/api/documents/{uuid.uuid4()}/file")

        assert response.status_code == 404


class TestDocumentCover:
    def test_serves_a_png_cover_with_its_sniffed_content_type(self):
        client = _client()
        document = _seed_with_cover(client, b"\x89PNG\r\n\x1a\n\x00cover")

        response = client.get(f"/api/documents/{document.id.value}/cover")

        assert response.status_code == 200
        assert response.headers["content-type"] == "image/png"
        assert response.content == b"\x89PNG\r\n\x1a\n\x00cover"

    def test_sniffs_a_jpeg_og_image_cover(self):
        # An article's og:image can be any format; the content type is read off the
        # bytes, not assumed to be the PDF renderer's PNG (ADR-028).
        client = _client()
        document = _seed_with_cover(client, b"\xff\xd8\xff\xe0jpegdata")

        response = client.get(f"/api/documents/{document.id.value}/cover")

        assert response.status_code == 200
        assert response.headers["content-type"] == "image/jpeg"

    def test_is_404_until_a_cover_has_been_rendered(self):
        client = _client()
        created = client.post(
            "/api/documents", data={"title": "Clean Code"}, files={"file": _PDF}
        ).json()

        response = client.get(f"/api/documents/{created['id']}/cover")

        assert response.status_code == 404

    def test_unknown_id_returns_404(self):
        client = _client()

        response = client.get(f"/api/documents/{uuid.uuid4()}/cover")

        assert response.status_code == 404


def _seed_with_cover(client: TestClient, image: bytes) -> Document:
    """Put an enriched document with a stored cover blob into the shared read seams."""
    overrides = client.app.dependency_overrides
    uow_factory = overrides[get_uow_factory]()
    storage = overrides[get_document_storage]()

    async def seed() -> Document:
        document = Document.create("Clean Code")
        document.apply_enrichment(authors="Robert C. Martin", year=2008, has_cover=True)
        async with uow_factory() as uow:
            await uow.documents.save(document)
            await uow.commit()
        await storage.put(document.cover_key, image)
        return document

    return asyncio.run(seed())


class TestDomainErrorMapping:
    def test_empty_title_returns_422(self):
        client = _client()

        response = client.post(
            "/api/documents", data={"title": "   "}, files={"file": _PDF}
        )

        assert response.status_code == 422

    def test_an_unmapped_domain_error_surfaces_as_500(self):
        # ADR-008's other half: a DomainError with no registry entry was never given a
        # client meaning, so it is an oversight and must not be dressed up as a 4xx.
        # BlobNotFound is the real inhabitant (a missing blob is a broken invariant);
        # a local subclass keeps the test independent of which errors stay unmapped.
        class Unmapped(DomainError):
            pass

        app = create_app()

        @app.get("/boom")
        async def boom() -> None:
            raise Unmapped("no registry entry")

        response = TestClient(app, raise_server_exceptions=False).get("/boom")

        assert response.status_code == 500
