from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from pagemaster.domain.document.exceptions import DocumentNotFound, InvalidDocumentTitle
from pagemaster.domain.exceptions import DomainError

#: Domain errors that carry a client meaning, mapped to their HTTP status. An
#: error absent here is a programming oversight, surfaced as 500 (ADR-008).
_STATUS_BY_ERROR: dict[type[DomainError], int] = {
    InvalidDocumentTitle: 422,
    DocumentNotFound: 404,
}


async def _handle_domain_error(request: Request, exc: DomainError) -> JSONResponse:
    for error_type, status in _STATUS_BY_ERROR.items():
        if isinstance(exc, error_type):
            return JSONResponse(status_code=status, content={"detail": str(exc)})
    raise exc  # unmapped: let it surface as 500


def register_exception_handlers(app: FastAPI) -> None:
    """Map domain errors to HTTP responses; the domain stays free of transport."""
    app.add_exception_handler(DomainError, _handle_domain_error)
