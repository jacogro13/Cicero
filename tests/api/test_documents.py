"""POST /api/documents + GET /api/documents over HTTP (ADR-005).

The routes are driven with the in-memory fakes injected through FastAPI's
``dependency_overrides`` seam, so the HTTP layer is verified without a real
adapter. One shared store/storage per client, so a POST is visible to a later GET.
"""

import uuid

from fastapi.testclient import TestClient

from cicero.domain.document.document_status import DocumentStatus
from cicero.entrypoints.dependencies import get_document_storage, get_uow_factory
from cicero.entrypoints.main import create_app

from tests.fakes import InMemoryDocumentStorage, make_in_memory_uow_factory

_PDF = ("clean-code.pdf", b"%PDF-1.4 bytes", "application/pdf")


def _client() -> TestClient:
    app = create_app()
    uow_factory = make_in_memory_uow_factory()
    storage = InMemoryDocumentStorage()
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


class TestDomainErrorMapping:
    def test_empty_title_returns_422(self):
        client = _client()

        response = client.post(
            "/api/documents", data={"title": "   "}, files={"file": _PDF}
        )

        assert response.status_code == 422
