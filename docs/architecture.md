# PageMaster — Architecture

> A living map of the system. It grows as capabilities are built; detailed
> decisions live in the [Architecture Decision Records](#decision-records), each
> written when its slice lands. Anything marked **Planned** is a committed
> direction, not yet implemented — its ADR is written when that slice is built.

## What PageMaster is

A self-contained personal library that turns documents into AI-generated
summaries you can read quickly. You add documents (PDF uploads or web articles);
PageMaster extracts their text and uses it as raw material to generate concise
summaries — per chapter for a book, or a single summary for an article — and
those summaries are what you read in the app (or chat with the document about;
articles can also be turned into a podcast). The extracted text itself is never
displayed; to read a source in full you open the original PDF or link. It runs
end to end from `docker compose up` with no external services: the database and
object storage are local containers, and the AI features use mock adapters
unless a real OpenAI-compatible endpoint is configured.

## Layering

The backend is **ports-and-adapters / DDD**, dependencies pointing inward —
`domain ← services ← adapters / entrypoints` — with the rule enforced in CI by
import-linter. See **[ADR-001](adr/001-hexagonal-ddd-layering.md)** for the full
rationale and the `src/pagemaster/` layout.

```mermaid
flowchart LR
    entrypoints["entrypoints<br/>FastAPI · wiring"]
    adapters["adapters<br/>DB · storage · LLM"]
    services["services<br/>use cases"]
    domain["domain<br/>entities · ports"]

    entrypoints --> services
    entrypoints --> adapters
    entrypoints --> domain
    services --> domain
    adapters --> domain

    classDef planned stroke-dasharray:5 5,fill:#f6f6f6,color:#555;
    class adapters planned
```

Arrows are *imports*; dashed nodes are **Planned** (not built yet).

| Layer | Responsibility | Status |
|-------|----------------|--------|
| `domain/` | Entities, value objects, ports — pure Python, no infra | **Exists** (`Document`, `DocumentId`, `DocumentStatus`; ports `DocumentRepository`, `UnitOfWork`, `DocumentStorage`) |
| `services/` | One use-case class per command; owns its Unit-of-Work transaction | **Exists** (`UploadDocument`, `ListDocuments`) |
| `adapters/` | Implements domain ports against real infra (DB, object storage, LLM) | **Planned** |
| `entrypoints/` | FastAPI app, routes, schemas, wiring | **Exists** (`GET /health`; `POST`/`GET /api/documents`) |

## Document lifecycle

`Document` is the aggregate root. Its status is a guarded state machine —
`UPLOADED → PROCESSING → READY | FAILED` — with transitions encapsulated as
entity methods, not a free `status` setter. The `content_key` (an opaque locator for
the internal extracted text, never shown to the reader) is set atomically when a
document becomes READY. See
**[ADR-002](adr/002-document-status-state-machine.md)**.

```mermaid
stateDiagram-v2
    [*] --> UPLOADED
    UPLOADED --> PROCESSING: mark_processing()
    PROCESSING --> READY: mark_ready(content_key)
    PROCESSING --> FAILED: mark_failed()
    READY --> [*]
    FAILED --> [*]
```

## Persistence: repositories and the Unit of Work

Persistence is reached through two domain **ports** (abstract interfaces; the
concrete adapters that implement them live outside the domain). A **repository**
is the collection for one *aggregate* — `DocumentRepository` (`save`,
`find_by_id`, `find_all`) for `Document`, under `domain/document/ports/`. The **`UnitOfWork`**
(under `domain/ports/`) is the transaction *scope*: an async context manager that
exposes one repository per aggregate (`uow.documents`, later `uow.notes` / …), so
a single block commits across all of them atomically. **Commit is explicit; any
other exit rolls back.** Services receive a `uow_factory` — a zero-arg callable
returning a fresh, unentered UoW — never a raw session. Today only an in-memory
implementation exists (a test double); real Postgres lands behind the *same*
ports later, with the save-and-fetch behaviour unchanged. See
**[ADR-003](adr/003-unit-of-work-and-repository-ports.md)**.

```mermaid
sequenceDiagram
    participant S as Service / caller
    participant U as UnitOfWork
    participant R as DocumentRepository
    S->>U: async with uow_factory() as uow
    S->>R: await uow.documents.save(doc)
    S->>U: await uow.commit()
    U-->>S: exit block (rollback if not committed)
```

## Uploading a document

The first use case lives in the `services/` layer. **`UploadDocument`** takes a
title and the source file's bytes; it stores the file first, then commits the
metadata in a Unit of Work — the deliberate ordering ADR-004 explains. The file's
location is `Document.source_key` (`documents/{id}/source`), a pure function of
identity, distinct from `content_key` (the extracted text). Storage is reached
through a third domain port, **`DocumentStorage`** (`domain/document/ports/`,
`put` for now), in-memory today and an S3-compatible adapter later. Dependencies
(`uow_factory`, `storage`) arrive as constructor parameters; upload leaves the
document `UPLOADED`. See
**[ADR-004](adr/004-object-storage-port-and-services-layer.md)**.

```mermaid
sequenceDiagram
    participant C as Caller (route, test, …)
    participant U as UploadDocument
    participant S as DocumentStorage
    participant W as UnitOfWork
    C->>U: await execute(title, content)
    U->>U: doc = Document.create(title)
    U->>S: await storage.put(doc.source_key, content)
    U->>W: async with uow_factory() as uow
    U->>W: await uow.documents.save(doc)
    U->>W: await uow.commit()
    U-->>C: return doc
```

## Exposing the use cases over HTTP

The `entrypoints/` layer puts the use cases on the wire. Routes live in an
`APIRouter` mounted under `/api` — `POST /api/documents` (a `multipart` `title` +
file upload) and `GET /api/documents` (the library list); `/health` stays
unprefixed. Each route is thin: parse the request, call the use case, map the
result to a **`DocumentResponse`** (`id`, `title`, `status`) — the wire shape that
deliberately omits the internal storage keys and extracted text. Use cases are
assembled in `dependencies.py` and injected with `Depends`; the leaf infra
providers (`uow_factory`, `storage`) are the swap point — they raise until a real
adapter lands, and tests override them with the in-memory fakes through FastAPI's
`dependency_overrides`, so the routes are verified with no infrastructure. See
**[ADR-005](adr/005-http-api-routing-schemas-and-di-seam.md)**.

```mermaid
sequenceDiagram
    participant C as HTTP client
    participant R as Route /api/documents
    participant D as dependencies.py
    participant U as UploadDocument
    C->>R: POST multipart (title, file)
    R->>D: Depends(get_upload_document)
    D-->>R: UploadDocument(uow_factory, storage)
    R->>U: await execute(title, content)
    U-->>R: Document
    R-->>C: 201 DocumentResponse (id, title, status)
```

## Planned capabilities

Each of these is a committed direction; its design decision is recorded in an ADR
when the slice is built test-first (so the ADR reflects real, validated code):

- **Persistence** — the repository + Unit-of-Work *ports* exist (see above), with
  an in-memory implementation; what remains is the real **Postgres** adapter for
  document metadata (including `content_key`) behind those same ports.
  _Adapter ADR to follow with the Postgres slice._
- **Object storage** — the `DocumentStorage` *port* exists (in-memory, holding
  uploaded source files keyed by `source_key`); what remains is the real
  **S3-compatible** (Garage) adapter and storing the **extracted content** keyed
  by `content_key` — the database keeps metadata and keys, never blobs.
  _Adapter ADR to follow with the storage slice._
- **Extraction** — turn a source into Markdown text: PDFs in-process via
  PyMuPDF, URLs via trafilatura/Playwright. This text is internal — the input to
  summarization, never shown to the user. Drives `PROCESSING → READY/FAILED`.
  _ADR to follow with the extraction slice._
- **AI summaries (the read experience)** — the extracted text is summarized into
  what the user actually reads: per-chapter summaries for a book, a single
  summary for an article. Built on top: chat over the document (any source) and,
  **for articles only (for now)**, a generated podcast (script + audio). Mock
  adapters by default (keeping the app self-contained);
  any OpenAI-compatible endpoint pluggable (optional Ollama compose profile).
  _ADRs to follow with those slices._
- **Frontends** — an admin SPA (upload/delete/trigger jobs) and a reader SPA
  (read/notes/chat). _ADRs to follow._

## What exists today

The repository is built incrementally and test-first, so this map runs ahead of
the code on purpose. Implemented so far:

- `GET /health` and the app/CI spine.
- The HTTP API (the `entrypoints/` layer): `POST /api/documents` (multipart
  upload) and `GET /api/documents` (list), mapping the domain to a
  `DocumentResponse` and wiring the use cases through a dependency-injection seam
  whose infra providers are overridden in tests until the real adapters land.
- The `Document` aggregate: a generated `DocumentId`, a validated title, and the
  status state machine.
- The persistence **ports** (`DocumentRepository`, `UnitOfWork`) with an
  in-memory implementation — save a document and fetch it back, with the
  Unit of Work as the transaction boundary.
- The first use cases (the `services/` layer): **`UploadDocument`**, over a
  `DocumentStorage` port — stores the source file (in-memory adapter) then
  persists the document, file-first so a failure can only orphan a blob — and
  **`ListDocuments`**, a read returning every stored document via
  `DocumentRepository.find_all`.

Everything under **Planned** above is direction, not code, yet.

## Decision records

ADRs live in [`docs/adr/`](adr/). Newest decisions reference earlier ones; none
references a decision made later.

- [ADR-001 — Hexagonal / DDD layering with a src-layout](adr/001-hexagonal-ddd-layering.md)
- [ADR-002 — Document status as a guarded state machine](adr/002-document-status-state-machine.md)
- [ADR-003 — Unit of Work and repository ports](adr/003-unit-of-work-and-repository-ports.md)
- [ADR-004 — Object-storage port and the services layer](adr/004-object-storage-port-and-services-layer.md)
- [ADR-005 — HTTP API routing, schemas, and the DI seam](adr/005-http-api-routing-schemas-and-di-seam.md)
