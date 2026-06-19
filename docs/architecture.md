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
```

Arrows are *imports*. `services` and `adapters` are independent siblings (neither
imports the other); the rule is enforced in CI by import-linter.

| Layer | Responsibility | Status |
|-------|----------------|--------|
| `domain/` | Entities, value objects, ports, errors — pure Python, no infra | **Exists** (`Document`, `DocumentId`, `DocumentStatus`; ports `DocumentRepository`, `UnitOfWork`, `DocumentStorage`, `DocumentExtractor`; `DomainError` hierarchy) |
| `services/` | One use-case class per command; owns its Unit-of-Work transaction | **Exists** (`UploadDocument`, `ListDocuments`, `DeleteDocument`, `ExtractDocument`) |
| `adapters/` | Implements domain ports against real infra (DB, object storage, extraction, LLM) | **Exists** (`PostgresDocumentRepository`, `SqlAlchemyUnitOfWork`, `S3DocumentStorage`, `PyMuPDFExtractor`; LLM to come) |
| `entrypoints/` | FastAPI app, routes, schemas, error mapping, wiring | **Exists** (`GET /health`; `POST`/`GET`/`DELETE /api/documents`) |

## Document lifecycle

`Document` is the aggregate root. Its status is a guarded state machine —
`UPLOADED → PROCESSING → READY | FAILED` — with transitions encapsulated as
entity methods, not a free `status` setter. `status` is the single source of truth
for readiness: the internal extracted text (an opaque locator, never shown to the
reader) exists when, and only when, the status is READY. `content_key` is not
lifecycle state — it is the identity-derived address of that text (`source_key`'s
twin), always computable, so nothing has to be set or kept in sync on transition.
See **[ADR-002](adr/002-document-status-state-machine.md)**.

```mermaid
stateDiagram-v2
    [*] --> UPLOADED
    UPLOADED --> PROCESSING: mark_processing()
    PROCESSING --> READY: mark_ready()
    PROCESSING --> FAILED: mark_failed()
    READY --> [*]
    FAILED --> [*]
```

## Persistence: repositories and the Unit of Work

Persistence is reached through two domain **ports** (abstract interfaces; the
concrete adapters that implement them live outside the domain). A **repository**
is the collection for one *aggregate* — `DocumentRepository` (`save`,
`find_by_id`, `find_all`, `delete`) for `Document`, under `domain/document/ports/`. The **`UnitOfWork`**
(under `domain/ports/`) is the transaction *scope*: an async context manager that
exposes one repository per aggregate (`uow.documents`, later `uow.notes` / …), so
a single block commits across all of them atomically. **Commit is explicit; any
other exit rolls back.** Services receive a `uow_factory` — a zero-arg callable
returning a fresh, unentered UoW — never a raw session. An in-memory implementation
backs unit tests; a **Postgres adapter** implements the same ports for real (below).
See **[ADR-003](adr/003-unit-of-work-and-repository-ports.md)**.

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

## Persisting to Postgres

The real implementation of those ports lives in the `adapters/` layer.
`SqlAlchemyUnitOfWork` wraps an async `AsyncSession` — one `async with` block is one
transaction, with the ADR-003 commit/rollback contract — and
`PostgresDocumentRepository` is `uow.documents` over that session. The domain
`Document` is persisted by **imperative mapping** declared entirely in the adapter
(`orm.py`): the entity keeps zero ORM imports (ADR-001), and a `TypeDecorator`
translates the `DocumentId` value object ↔ a UUID column. The adapter is verified
against **real Postgres in a throwaway testcontainer** — the `tests/integration/`
layer (`make integration`), re-running the ADR-003 save/fetch/rollback behaviours
unchanged, so the database is a proven swappable adapter rather than a mock. Wiring
the *running* app to Postgres (settings, engine lifespan, schema, a compose service)
is a later slice; the in-memory fake still backs the fast unit/API suite. See
**[ADR-006](adr/006-postgres-persistence-adapter.md)**.

## Storing files in object storage

The `DocumentStorage` port's real implementation is **`S3DocumentStorage`** — an
**S3-compatible** client (Garage / MinIO / AWS — endpoint-agnostic, same code for
the self-contained stack and a cloud bucket). boto3 is synchronous, so each call is
offloaded to the **anyio worker thread** to keep the event loop free; the adapter
assumes its bucket exists (provisioned out of band), as the Postgres adapter assumes
its schema does. It ships `put`, `get`, and `delete` (the port's surface), proven against a **real
MinIO testcontainer** in `tests/integration/` (`make integration`) — a fresh bucket
per test, the round-trip read back through a separate client. Live wiring (endpoint,
keys, bucket from settings; a compose object-store service) is deferred to the
composition-root slice alongside Postgres. See
**[ADR-007](adr/007-s3-object-storage-adapter.md)**.

## Uploading a document

The first use case lives in the `services/` layer. **`UploadDocument`** takes a
title and the source file's bytes; it stores the file first, then commits the
metadata in a Unit of Work — the deliberate ordering ADR-004 explains. The file's
location is `Document.source_key` (`documents/{id}/source`), a pure function of
identity, distinct from `content_key` (the extracted text). Storage is reached
through a third domain port, **`DocumentStorage`** (`domain/document/ports/`),
in-memory in tests and an S3-compatible adapter for real (above).
Dependencies
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

## Deleting a document

**`DeleteDocument`** removes a document's metadata and then its source file — the
exact mirror of upload's ordering (ADR-004): committing the delete first and
removing the blob after means the only possible inconsistency is a harmless
orphaned blob, never a metadata row pointing at a missing file. An unknown id
raises `DocumentNotFound`. `DELETE /api/documents/{id}` returns 204.

## Extracting a document

**`ExtractDocument`** turns an uploaded source into the internal Markdown that
summarization will read (never shown to the reader). It drives the rest of the
status machine for real: it commits `PROCESSING` first (so the in-flight state is
observable), runs the heavy I/O outside any transaction — read the source bytes
(`DocumentStorage.get`), extract Markdown (the new **`DocumentExtractor`** port),
write the result blob to `document.content_key` — then commits `READY`. The
service never mints a storage key: `content_key` is the document's own
identity-derived address (`documents/{id}/content`). Storage-first mirrors upload
(ADR-004): the blob is written before `READY` is committed, so a READY document
never points at a missing content file. Extraction failure commits `FAILED` (status is the outcome channel
for the background job to come); an unknown id raises `DocumentNotFound`. The real
extractor is **`PyMuPDFExtractor`** (`pymupdf4llm`, in-process, offloaded to the
anyio thread); a stub backs the unit tests. See
**[ADR-009](adr/009-content-extraction-and-the-extract-document-use-case.md)**.

```mermaid
sequenceDiagram
    participant U as ExtractDocument
    participant W as UnitOfWork
    participant S as DocumentStorage
    participant E as DocumentExtractor
    U->>W: commit mark_processing()
    U->>S: source = await get(source_key)
    U->>E: markdown = await extract_markdown(source)
    alt extraction succeeds
        U->>S: await put(document.content_key, markdown)
        U->>W: commit mark_ready()
    else extraction fails
        U->>W: commit mark_failed()
    end
```

## Errors: the domain raises, the entrypoints map

Domain failures are a small `DomainError` hierarchy (`InvalidDocumentTitle`,
`DocumentNotFound`) raised where the rule lives; the domain never names an HTTP
status (ADR-001). A single registry in `entrypoints/errors.py` maps each to a
response — `InvalidDocumentTitle → 422`, `DocumentNotFound → 404` — so the status
codes live in one place and an unmapped domain error surfaces as 500 by design.
See **[ADR-008](adr/008-domain-exceptions-and-http-error-mapping.md)**.

## Exposing the use cases over HTTP

The `entrypoints/` layer puts the use cases on the wire. Routes live in an
`APIRouter` mounted under `/api` — `POST /api/documents` (a `multipart` `title` +
file upload), `GET /api/documents` (the library list), and
`DELETE /api/documents/{id}` (→ 204); `/health` stays
unprefixed. Each route is thin: parse the request, call the use case, map the
result to a **`DocumentResponse`** (`id`, `title`, `status`) — the wire shape that
deliberately omits the internal storage keys and extracted text. Domain failures
raised by the use cases are turned into responses by the error registry (see
"Errors: the domain raises, the entrypoints map"). Use cases are
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

- **Live persistence wiring** — the Postgres adapter exists and is proven (see
  "Persisting to Postgres"); what remains is connecting it to the *running* app:
  settings/`DATABASE_URL`, an engine lifespan, schema management, and a Postgres
  service in the compose stack. Until then `get_uow_factory` stays a seam the API
  tests override with the in-memory fake. _ADR to follow with that slice._
- **Object storage** — the `DocumentStorage` port and its **S3-compatible adapter**
  both exist and store source files (`source_key`) and extracted content
  (`content_key`); the database keeps metadata only, never blobs, and the keys are
  identity-derived addresses, not stored columns. What remains
  is the live wiring (see "Live persistence wiring", shared with Postgres). _ADRs
  to follow._
- **URL ingest** — extraction handles PDFs (see "Extracting a document"); adding a
  web article as a document (trafilatura/Playwright) extends the `DocumentExtractor`
  port when that slice lands. _ADR to follow._
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
  upload), `GET /api/documents` (list), and `DELETE /api/documents/{id}` (204),
  mapping the domain to a `DocumentResponse`, turning `DomainError`s into HTTP
  statuses through one registry, and wiring the use cases through a
  dependency-injection seam whose infra providers are overridden in tests until
  the real adapters land.
- The `Document` aggregate: a generated `DocumentId`, a validated title, and the
  status state machine.
- The persistence **ports** (`DocumentRepository`, `UnitOfWork`) with two
  implementations: the in-memory fake for unit tests, and a **Postgres adapter**
  (`adapters/persistence/`, SQLAlchemy + imperative mapping) proven against a real
  database in the `tests/integration/` layer (`make integration`).
- The object-storage **port** (`DocumentStorage`, `put`/`get`/`delete`) with two
  implementations: the in-memory fake for unit tests, and an **S3-compatible adapter**
  (`adapters/storage/`, boto3 in the anyio thread pool) proven against a real MinIO
  container in the `tests/integration/` layer.
- The extraction **port** (`DocumentExtractor`) with two implementations: a stub
  for unit tests, and **`PyMuPDFExtractor`** (`adapters/extraction/`, `pymupdf4llm`
  in-process) proven against a real generated PDF in the `tests/integration/` layer.
- The use cases (the `services/` layer): **`UploadDocument`**, over the
  `DocumentStorage` port — stores the source file then persists the document,
  file-first so a failure can only orphan a blob; **`ListDocuments`**, a read
  returning every stored document via `DocumentRepository.find_all`;
  **`DeleteDocument`**, which removes metadata then the source blob (the mirror of
  upload's ordering) and raises `DocumentNotFound` for an unknown id; and
  **`ExtractDocument`**, which drives `PROCESSING → READY/FAILED`, storing the
  extracted Markdown at `content_key` (file-first, like upload).

Everything under **Planned** above is direction, not code, yet.

## Decision records

ADRs live in [`docs/adr/`](adr/). Newest decisions reference earlier ones; none
references a decision made later.

- [ADR-001 — Hexagonal / DDD layering with a src-layout](adr/001-hexagonal-ddd-layering.md)
- [ADR-002 — Document status as a guarded state machine](adr/002-document-status-state-machine.md)
- [ADR-003 — Unit of Work and repository ports](adr/003-unit-of-work-and-repository-ports.md)
- [ADR-004 — Object-storage port and the services layer](adr/004-object-storage-port-and-services-layer.md)
- [ADR-005 — HTTP API routing, schemas, and the DI seam](adr/005-http-api-routing-schemas-and-di-seam.md)
- [ADR-006 — Postgres persistence adapter (SQLAlchemy + testcontainers)](adr/006-postgres-persistence-adapter.md)
- [ADR-007 — S3-compatible object-storage adapter (boto3 in an anyio thread pool)](adr/007-s3-object-storage-adapter.md)
- [ADR-008 — Domain exceptions and domain→HTTP error mapping](adr/008-domain-exceptions-and-http-error-mapping.md)
- [ADR-009 — Content extraction (PDF → Markdown) and the ExtractDocument use case](adr/009-content-extraction-and-the-extract-document-use-case.md)
