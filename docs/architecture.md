# Cicero — Architecture

> A living map of the system. It grows as capabilities are built; detailed
> decisions live in the [Architecture Decision Records](#decision-records), each
> written when its slice lands. Anything marked **Planned** is a committed
> direction, not yet implemented — its ADR is written when that slice is built.

## What Cicero is

A self-contained personal library that turns documents into AI-generated
summaries you can read quickly. You add documents (PDF uploads or web articles);
Cicero extracts their text and uses it as raw material to generate concise
summaries — per chapter for a book, or a single summary for an article — and
those summaries are what you read in the app (or chat with the document about;
articles can also be turned into a podcast). The extracted text itself is never
displayed to readers; to read a source in full you open the original PDF or link
(an operator can inspect the extracted text in the admin console, to verify
extraction). It runs
end to end from `docker compose up` with no external services: the database and
object storage are local containers, and the AI features use mock adapters
unless a real OpenAI-compatible endpoint is configured.

## Layering

The backend is **ports-and-adapters / DDD**, dependencies pointing inward —
`domain ← services ← adapters / entrypoints` — with the rule enforced in CI by
import-linter. See **[ADR-001](adr/001-hexagonal-ddd-layering.md)** for the full
rationale and the `src/cicero/` layout.

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
| `domain/` | Entities, value objects, ports, messages, errors — pure Python, no infra | **Exists** (`Document`, `DocumentId`, `DocumentStatus`, `Chapter`, the pure `chapter_ranges`; messages `Command`/`Event` + `Upload`/`Extract`/`Summarise`/`Delete` commands, `DocumentEvent` base + `DocumentUploaded`/`ExtractionCompleted`/`DocumentProcessingFailed` events; ports `DocumentRepository`, `UnitOfWork`, `DocumentStorage`, `DocumentExtractor`, `DocumentSummarizer`, `ChapterReadModel`, `SummaryReadModel`; `DomainError` hierarchy) |
| `services/` | Command/event handlers + the message bus that routes them, and the read-side `views` that bypass it | **Exists** (`MessageBus`; command handlers `UploadDocument`, `DeleteDocument`, `ExtractDocument`, `SummariseDocument`; the `AdvanceDocument` event handler on `DocumentUploaded`/`ExtractionCompleted`; `views.list_documents`/`get_document_summary`/`get_document_chapters` returning read models) |
| `adapters/` | Implements domain ports against real infra (DB, object storage, extraction, LLM) | **Exists** (`PostgresDocumentRepository`, `PostgresChapterReadModel`, `PostgresSummaryReadModel`, `SqlAlchemyUnitOfWork`, `S3DocumentStorage`, `PyMuPDFExtractor`, `MockSummarizer` + `OpenAISummarizer`) |
| `entrypoints/` | FastAPI app, routes, schemas, error mapping, the serial job queue, the composition root (settings, engine lifespan, startup provisioning, bus bootstrap) | **Exists** (`GET /health`; `POST`/`GET`/`DELETE /api/documents`, `GET /api/documents/{id}/summary` + `/chapters`; `JobQueue` + the `NEXT_COMMAND` stage table + restart recovery; live wiring over Postgres + S3) |

## Document lifecycle

`Document` is the aggregate root. Its status is a guarded state machine —
`UPLOADED → EXTRACTING → EXTRACTED → SUMMARISING → SUMMARISED`, with `FAILED` the
single terminal any stage falls to — with transitions encapsulated as entity
methods, not a free `status` setter. Each member names the **pipeline stage
reached**, not readiness (ADR-014): that is what lets the edge derive the next
command from a stored status, and what lets a later stage append to the chain
instead of redefining a terminal name. The internal extracted text — split into **chapters** at the PDF's own bookmarks,
never shown to the reader — exists from EXTRACTED onwards; the per-chapter summaries,
the read experience, from SUMMARISED. Chapter *content* lives in object storage at
identity-derived keys (`chapter_key(i)`, `source_key`'s twins, always computable); the
chapter *titles* — the table of contents — in a read model. Neither is lifecycle
state, so nothing content-shaped has to be kept in sync on transition. The
aggregate also carries a **`kind`** (`BOOK`/`ARTICLE`) — a browsing classification
the reader splits on, derived from the source at ingest and read by no pipeline
stage (ADR-026). See
**[ADR-002](adr/002-document-status-state-machine.md)**,
**[ADR-014](adr/014-status-driven-pipeline-advance.md)**,
**[ADR-016](adr/016-ai-summaries-and-the-summary-read-model.md)**,
**[ADR-021](adr/021-chapters-from-the-pdf-table-of-contents.md)**, and
**[ADR-026](adr/026-document-kind.md)**.

```mermaid
stateDiagram-v2
    [*] --> UPLOADED
    UPLOADED --> EXTRACTING: mark_extracting()
    EXTRACTING --> EXTRACTED: mark_extracted()
    EXTRACTED --> SUMMARISING: mark_summarising()
    SUMMARISING --> SUMMARISED: mark_summarised()
    EXTRACTING --> FAILED: mark_failed()
    SUMMARISING --> FAILED: mark_failed()
    SUMMARISED --> [*]
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
unchanged, so the database is a proven swappable adapter rather than a mock. The
*running* app is wired to this adapter in the composition root (see "Running the
app"); the in-memory fake still backs the fast unit/API suite. See
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
keys, bucket from settings; the bucket provisioned at startup; a compose object-store
service) lands in the composition root (see "Running the app"). See
**[ADR-007](adr/007-s3-object-storage-adapter.md)**.

## Uploading a document

The first use case is a **command handler** in the `services/` layer.
**`UploadDocument`** handles a `commands.UploadDocument` (title + source bytes): it
stores the file first, then commits the metadata in a Unit of Work — the deliberate
ordering ADR-004 explains. The file's location is `Document.source_key`
(`documents/{id}/source`), a pure function of identity, distinct from the chapter
keys `chapter_key(i)` (the extracted text). Storage is reached through a third domain port,
**`DocumentStorage`** (`domain/document/ports/`), in-memory in tests and an
S3-compatible adapter for real (above). Storage is injected at bootstrap; the bus
supplies the Unit of Work per call. Upload leaves the document `UPLOADED` and the
aggregate records a `DocumentUploaded` event (see "Orchestration"). See
**[ADR-004](adr/004-object-storage-port-and-services-layer.md)**.

```mermaid
sequenceDiagram
    participant B as MessageBus
    participant U as UploadDocument handler
    participant S as DocumentStorage
    participant W as UnitOfWork
    B->>U: await handler(command, uow)
    U->>U: doc = Document.create(title) records DocumentUploaded
    U->>S: await storage.put(doc.source_key, content)
    U->>W: async with uow
    U->>W: await uow.documents.save(doc)
    U->>W: await uow.commit()
    U-->>B: return doc
```

## Orchestration: the message bus

Use cases are reached through one entry point, **`MessageBus.handle()`** (ADR-011).
A **`Command`** (imperative — `commands.UploadDocument`) is routed to exactly one
handler; an **`Event`** (a past-tense fact — `DocumentUploaded`) to zero or more.
Messages are pure data in the domain (`domain/<agg>/commands.py` + `events.py`,
bases in `domain/messages.py`). The **aggregate is the event source**: `Document`
records events off its own lifecycle (`create()` → `DocumentUploaded`;
`mark_extracted()` → `ExtractionCompleted`; `mark_failed()` →
`DocumentProcessingFailed`). After each handler
the bus **drains the Unit of Work's new events** — `collect_new_events()` reads them
off the aggregates the repository has `seen` (registered by the port itself on
every accessor, delete included) — and keeps
processing until the queue empties, so one upload can fan out into a chain of
reactions. Handlers stay class-based use cases, callable as `(message, uow)`; the
composition root **bootstraps** them (injecting deps, building the command/event
maps) and hands the bus to the routes. The bus carries **writes only** — reads
bypass it (see "Reading: the CQRS read side").

The pipeline is wired as events. New messages reach the queue **only** as events the
aggregates raise — a handler never synthesises a command, so **commands enter at the
edge**. Internal reactions are event handlers: **`AdvanceDocument`** subscribes to
`DocumentUploaded` and puts the document on the job queue, so upload *causes*
extraction without the route knowing extraction exists — and without the handler
naming extraction either, since it enqueues a bare id. The command surface is now
issued from two edges — the routes (`UploadDocument`, `DeleteDocument`) and the
**job-queue worker** (`ExtractDocument`, see "Background jobs").
See **[ADR-011](adr/011-message-bus-commands-and-events.md)**,
**[ADR-012](adr/012-pipeline-as-events.md)**, and
**[ADR-013](adr/013-serial-job-queue-and-restart-recovery.md)**.

## Reading: the CQRS read side

Reads **bypass the bus** (ADR-015). A **`services/views.py`** query module holds
functions that take the `uow_factory`, open a short read-only transaction, and return
a **read model** — no command, no commit. `views.list_documents` → `list[DocumentView]`
(`GET /api/documents`) still reads through the aggregate repository, since a document
list does not diverge from the aggregate. `views.get_document_summary` →
`SummaryView | None` (`GET /api/documents/{id}/summary`, 404 when absent) joins the
per-chapter summaries from the **denormalized `summaries` store** for admin inspection;
`views.get_document_chapters` → `list[ChapterView]` (`GET /api/documents/{id}/chapters`)
zips the **`chapters` store** (the table of contents) with those summaries — the
reader's structured read side. Both stores are denormalized read models maintained by
the pipeline stages (ADR-016/021), decoupled from both the domain `Document` (the write
model) and the wire **DTO** (`DocumentResponse`/`SummaryResponse`/`ChapterResponse`) —
the seam that lets the reader experience diverge from the aggregate. See
**[ADR-015](adr/015-cqrs-read-side.md)**,
**[ADR-016](adr/016-ai-summaries-and-the-summary-read-model.md)**, and
**[ADR-021](adr/021-chapters-from-the-pdf-table-of-contents.md)**.

## Deleting a document

**`DeleteDocument`** removes a document's metadata and then its source file — the
exact mirror of upload's ordering (ADR-004): committing the delete first and
removing the blob after means the only possible inconsistency is a harmless
orphaned blob, never a metadata row pointing at a missing file. An unknown id
raises `DocumentNotFound`. `DELETE /api/documents/{id}` returns 204.

## Extracting a document

**`ExtractDocument`** is a **command handler**, issued by the job-queue worker off
the request path (see "Background jobs"), not by a route. It turns an uploaded source into the
internal Markdown that summarization will read (never shown to the reader), driving
the rest of the status machine for real: it commits `EXTRACTING` first (so the
in-flight state is observable), runs the heavy I/O outside any transaction — read the
source bytes (`DocumentStorage.get`), split into **chapters** at the PDF's level-1
bookmarks and render each to Markdown (the **`DocumentExtractor`** port, returning
`list[Chapter]`; no bookmarks → one chapter, the article/fallback shape), write each
chapter's blob to `document.chapter_key(i)` — then commits `EXTRACTED` *with* the
ordered chapter titles (`uow.chapters`), raising `ExtractionCompleted` (the fact
summaries subscribe to). Boundaries come from the PDF's table of contents via the pure
`chapter_ranges` domain function, kept distinct from the PyMuPDF rendering. The service
never mints a storage key: `chapter_key(i)` is the document's own identity-derived
address (`documents/{id}/chapters/{i}`, `source_key`'s twin). Storage-first mirrors
upload (ADR-004): the chapter blobs are written before `EXTRACTED` is committed, so an
EXTRACTED document never points at a missing chapter. Extraction failure commits
`FAILED` and raises `DocumentProcessingFailed` (status is the outcome channel); an
unknown id raises `DocumentNotFound`. The real extractor is **`PyMuPDFExtractor`**
(`pymupdf4llm`, in-process, offloaded to the anyio thread); a stub backs the unit
tests. See **[ADR-009](adr/009-content-extraction-and-the-extract-document-use-case.md)**,
**[ADR-012](adr/012-pipeline-as-events.md)**, and
**[ADR-021](adr/021-chapters-from-the-pdf-table-of-contents.md)**.

```mermaid
sequenceDiagram
    participant U as ExtractDocument
    participant W as UnitOfWork
    participant S as DocumentStorage
    participant E as DocumentExtractor
    U->>W: commit mark_extracting()
    U->>S: source = await get(source_key)
    U->>E: chapters = await extract(source)
    alt extraction succeeds
        U->>S: await put(chapter_key(i), chapter.markdown) — per chapter
        U->>W: commit titles (uow.chapters) + mark_extracted()
    else extraction fails
        U->>W: commit mark_failed()
    end
```

## Summarising a document

**`SummariseDocument`** is the next stage on the same conveyor — a command handler the
worker issues once a document reaches `EXTRACTED`. It mirrors extraction: commit
`SUMMARISING` first, then **summarise each chapter** from its own stored Markdown
through the **`DocumentSummarizer`** port outside any transaction, then commit
`SUMMARISED`. The summaries are the **read experience**, so unlike the internal
extracted text they are persisted as a **read model** — the transaction writes each
chapter's summary to `uow.summaries` (keyed by chapter) *with* `mark_summarised`, so
`SUMMARISED` ⇔ the summaries are readable (no partial state a reader could hit).
Failure commits `FAILED`; an unknown id raises `DocumentNotFound`.
The default adapter is **`MockSummarizer`** (canned text, self-contained — the app
summarises with no external LLM); **`OpenAISummarizer`** plugs in behind the same port
when `LLM_BASE_URL` names any OpenAI-compatible endpoint, config-selected in the
composition root so turnkey `docker compose up` stays key-free (ADR-018). A document
chapter larger than the model's context window is summarised by **map-reduce** (ADR-020): a
pure `split_for_budget` chunker (`domain/document/content_chunking.py` — greedy
paragraph packing, fenced code kept atomic) slices it, each slice is summarised, and
the parts are synthesised into one summary; input that fits stays a single call. The
chunker is framework-free domain code, placed there so the future retrieval index can
reuse it. Wiring the stage cost one status pair, one `NEXT_COMMAND` entry, and one
subscription of `AdvanceDocument` to `ExtractionCompleted` — the bus payoff. See
**[ADR-016](adr/016-ai-summaries-and-the-summary-read-model.md)**,
**[ADR-018](adr/018-openai-compatible-summarizer-adapter.md)**, and
**[ADR-020](adr/020-map-reduce-summarization-for-oversized-documents.md)**.

## Background jobs: the serial queue

Extraction (and the summaries and podcast ahead) is slow and memory-heavy, so it
runs **off the request path** on a process-wide serial **`JobQueue`**
(`entrypoints/`). Workers drain enqueued **`DocumentId` intents** with a fixed
`concurrency` (default 1 → one document at a time), so a batch upload can enqueue
freely without ever running more than N heavy jobs at once — the memory guard.

The wiring keeps commands at the edge. `AdvanceDocument` — subscribed to each stage's
completion event (`DocumentUploaded`, `ExtractionCompleted`, …) — only enqueues an
intent and names no stage; the **worker** reads the document's persisted status back
and issues the command that status calls for, so the command is born at an entrypoint,
never synthesised in a handler. Each completed stage re-enqueues the document, so it
walks the whole chain — upload *causes* extraction *causes* summarization — without any
stage knowing the next. Upload returns immediately as `UPLOADED`; the document reaches
`SUMMARISED`/`FAILED` asynchronously (clients poll `GET`). The queue lives on
`app.state`, created per event loop in the lifespan.

**The pipeline's order lives in one table**, `NEXT_COMMAND` in
`entrypoints/pipeline.py`, mapping each status to the command that advances it (or to
`None` — the document is done and the intent is dropped). It is total over
`DocumentStatus`, so a new status without a decision fails a test rather than stalling
a document silently. Adding a stage therefore costs one status, one entry here, and one
subscription of `AdvanceDocument` to the preceding event — no new handler class and no
branch in the composition root.

An in-process queue loses whatever was mid-flight on a restart, so startup runs
**`reconcile_unfinished_documents`**: it re-enqueues every document whose status still
has a next stage, reconstructing the outstanding work from persisted status with no jobs
table. Because that is the *same* question ordinary dispatch asks, recovery is not a
separate path — and it also catches a document whose enqueue never happened. See
**[ADR-013](adr/013-serial-job-queue-and-restart-recovery.md)** and
**[ADR-014](adr/014-status-driven-pipeline-advance.md)**.

```mermaid
sequenceDiagram
    participant R as Route
    participant B as MessageBus
    participant Q as JobQueue
    participant K as Worker
    R->>B: handle(UploadDocument)
    B->>B: DocumentUploaded → AdvanceDocument
    B->>Q: enqueue(document_id)
    R-->>R: 201 UPLOADED (returns now)
    loop until a terminal status
        Q->>K: document_id
        K->>K: read status → NEXT_COMMAND
        K->>B: handle(Extract/Summarise…)
        B->>B: run the stage — its completion event re-enqueues via AdvanceDocument
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
file upload), `GET /api/documents` (the library list),
`GET /api/documents/{id}/summary` (admin: the per-chapter summaries joined, 404 until
summarised), `GET /api/documents/{id}/chapters` (the reader's table of contents with
per-chapter summaries), `GET /api/documents/{id}/content` (admin inspection: the
chapters assembled under their titles as `text/markdown`, 404 until EXTRACTED) and
`GET /api/documents/{id}/file` (the original PDF as `application/pdf`), and
`DELETE /api/documents/{id}` (→ 204); `/health` stays
unprefixed. Each route is thin: parse the request, call the use case, map the
result to a **`DocumentResponse`** (`id`, `title`, `status`) — the wire shape that
deliberately omits the internal storage keys and extracted text. **Write routes go
through the message bus**, issuing a command (`commands.UploadDocument` /
`DeleteDocument`); `bus.handle()` returns the originating command's result the route
serializes. The **read routes** (`GET`) instead bypass the bus, calling a `views.*`
query off the injected `uow_factory` (ADR-015). Most read a Postgres projection
(the list, the summary, the chapters); the **content/file viewers** instead read
**blobs** off the `DocumentStorage` port at the document's `chapter_key(i)`/`source_key`
— the content view assembling the chapters under their titles — and stream with an
honest content-type, so the read side injects `storage` too (ADR-019/021).
Domain failures raised by the handlers are turned into
responses by the error registry (see "Errors: the domain raises, the entrypoints
map"). The bus is bootstrapped in `dependencies.py` and injected with `Depends`; the
leaf infra providers (`uow_factory`, `storage`, `extractor`) are the swap point — wired
to the real adapters in the composition root (see "Running the app"), and overridden
with the in-memory fakes in tests through FastAPI's `dependency_overrides`, so the
routes are verified with no infrastructure. See
**[ADR-005](adr/005-http-api-routing-schemas-and-di-seam.md)**.

```mermaid
sequenceDiagram
    participant C as HTTP client
    participant R as Route /api/documents
    participant D as dependencies.py
    participant B as MessageBus
    C->>R: POST multipart (title, file)
    R->>D: Depends(get_message_bus)
    D-->>R: MessageBus (bootstrapped handlers)
    R->>B: await handle(commands.UploadDocument(title, content))
    B-->>R: Document
    R-->>C: 201 DocumentResponse (id, title, status)
```

## Running the app: the composition root

The `entrypoints/` layer is also where everything is assembled into a running
process — the composition root (`dependencies.py` + the app `lifespan`).
Configuration is read once from the environment into **`Settings`** (`pydantic-settings`:
`DATABASE_URL` + `S3_*`; no secrets in code). The root owns **one async engine per
process**, builds the real `UnitOfWork` factory and `S3DocumentStorage` from settings
— **retiring the `NotImplementedError` infra seams** — and disposes the engine on
shutdown. On **startup it provisions the infrastructure the adapters assume**:
`alembic upgrade head` migrates the schema and `ensure_bucket()` ensures the object
store, both idempotent (Alembic replaced startup `create_all` once the schema began to
evolve under real data — ADR-024; migration `0002` adds the `kind` column, the first
real `ALTER`). It then **builds the process-wide message bus**
(`app.state.bus`, the `get_message_bus` seam tests swap wholesale) and **starts the job
queue**, re-enqueuing any interrupted extraction (ADR-013). The whole thing runs from
`docker compose up`: Postgres + MinIO + the api, gated on health, zero external
services. See **[ADR-010](adr/010-composition-root-settings-and-startup-provisioning.md)**,
**[ADR-013](adr/013-serial-job-queue-and-restart-recovery.md)**, and
**[ADR-024](adr/024-alembic-migrations.md)**.

```mermaid
sequenceDiagram
    participant L as App lifespan
    participant D as dependencies.py
    participant E as Engine / Postgres
    participant S as S3DocumentStorage / MinIO
    participant Q as JobQueue
    L->>D: provision_infrastructure()
    D->>E: alembic upgrade head (idempotent)
    D->>S: ensure_bucket (idempotent)
    L->>D: build_message_bus → app.state.bus
    L->>Q: start(worker) + reconcile unfinished
    Note over L: yield — app serves requests, queue drains jobs
    L->>Q: stop() on shutdown
    L->>D: dispose_engine() on shutdown
```

## The frontends: reader and admin

Two user-facing surfaces split **by role**: the **reader** — the daily-use read
experience, at the root `/` — and the **admin console** at `/admin` (upload, list,
delete, inspect the raw extraction). They share one **`frontend/` tree, outside the
hexagon**: React + TypeScript built by Vite, tested with Vitest + Testing Library,
styled with CSS Modules, routed by react-router. The split is **by route, not by build
artifact** — one bundle, one client, one CI node job; import-linter governs the Python
layers only. A hardened boundary (auth, perhaps a separate deploy) is a later decision.

Both talk to the backend over **same-origin `/api`**, never a cross-origin call. In
development the Vite dev server proxies `/api` to the api on `:8000`; in production a
dedicated **`web` (nginx) compose service** serves the built bundle and reverse-proxies
`/api` to the api — so the api image stays decoupled from the frontend build and no
CORS config is needed. nginx serves the app shell for any non-file route, so deep links
(`/documents/:id`) survive a refresh. `docker compose up` brings the UI up with the stack.

```mermaid
flowchart LR
    B["Browser<br/>reader / · admin /admin"]
    W["web (nginx)<br/>serves dist · proxies /api"]
    A["api (FastAPI)"]
    B -->|same-origin /api| W
    W -->|/api| A
```

**Server state runs through TanStack Query.** The document list is a polled query — it
refetches while any document is still non-terminal and goes idle once every document is
`SUMMARISED`/`FAILED`, the client-side stand-in for the still-deferred push channel;
the reader's chapter view polls the same way while any chapter awaits its summary.
Upload and delete are admin mutations that invalidate the list. The **reader** lists the
library and, per document, navigates chapters by their table of contents
(`GET /api/documents/{id}/chapters`), reading each chapter's summary as Markdown —
extracted text stays admin-only. Testing is **pragmatic** — component tests drive the
flows against a mocked client, no backend-style red→green ceremony — and above them a
**black-box Playwright layer** (`e2e/`) drives the real compose stack end to end, one
spec accruing per frontend slice (ADR-025). See
**[ADR-017](adr/017-admin-spa-first-frontend-and-serving-topology.md)**,
**[ADR-022](adr/022-the-reader-spa-and-the-role-split.md)**, and
**[ADR-025](adr/025-end-to-end-tests-with-playwright.md)**.

## Planned capabilities

Each of these is a committed direction; its design decision is recorded in an ADR
when the slice is built test-first (so the ADR reflects real, validated code):

- **URL ingest** — extraction handles PDFs (see "Extracting a document"); adding a
  web article as a document (trafilatura/Playwright) extends the `DocumentExtractor`
  port when that slice lands. _ADR to follow._
- **AI summaries (the read experience)** — **per-chapter** summaries exist (see
  "Summarising a document"), each map-reduced when it overflows the model's context
  (ADR-020); a one-chapter document — an article, or a book with no TOC — collapses to
  a single summary. Still ahead: document **kind** (book/article). Built
  on top: chat over the document (any source) and, **for articles only (for now)**, a
  generated podcast (script + audio). Mock adapters by default (self-contained); any
  OpenAI-compatible endpoint pluggable (optional Ollama compose profile).
  _ADRs to follow with those slices._
- **Reader SPA** — the reading surface exists as an MVP (library + per-chapter TOC
  navigation, summaries read as Markdown; see "The frontends: reader and admin"). Still
  ahead: notes and chat, grown as the thin frontend tail of each read-shaped slice.
  _ADRs to follow with those slices._

## What exists today

The repository is built incrementally and test-first, so this map runs ahead of
the code on purpose. Implemented so far:

- `GET /health` and the app/CI spine.
- The HTTP API (the `entrypoints/` layer): `POST /api/documents` (multipart
  upload), `GET /api/documents` (list), and `DELETE /api/documents/{id}` (204),
  mapping the domain to a `DocumentResponse`, turning `DomainError`s into HTTP
  statuses through one registry, and reaching the use cases through the message bus,
  which tests swap wholesale at the `get_message_bus` seam with a bus wired over fakes.
- The `Document` aggregate: a generated `DocumentId`, a validated title, the
  status state machine, and a `kind` (`BOOK`/`ARTICLE`) browsing classification.
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
- The summarization **port** (`DocumentSummarizer`) with two implementations: a stub
  for unit tests, and the self-contained **`MockSummarizer`** (`adapters/summarization/`).
- The **message bus** (the `services/` layer): one `MessageBus.handle()` routes a
  `Command` to its single handler and an `Event` to zero or more, draining the
  Unit of Work's new events after each handler. The `Document` aggregate raises the
  events (`DocumentUploaded` on `create()`, `ExtractionCompleted` /
  `DocumentProcessingFailed` on the outcome). Commands enter only at the edge; internal
  reactions are events, so **upload causes extraction causes summarization** by
  `AdvanceDocument` subscribing to each stage's completion event — no route-level
  coupling, and no stage named in a handler.
- The use cases (the `services/` layer): **`UploadDocument`**, over the
  `DocumentStorage` port — stores the source file then persists the document,
  file-first so a failure can only orphan a blob; and **`DeleteDocument`**, which
  removes metadata then the source blob (the mirror of upload's ordering) and raises
  `DocumentNotFound` for an unknown id — both command handlers reached through the bus.
  **`ExtractDocument`**, a command handler issued by the job-queue worker, drives
  `EXTRACTING → EXTRACTED/FAILED`, splitting the PDF into chapters at its bookmarks and
  storing each at `chapter_key(i)` with the titles in the `chapters` read model
  (file-first, like upload). **`SummariseDocument`**, the next worker-issued stage,
  drives `SUMMARISING → SUMMARISED/FAILED`, writing the per-chapter summary read models
  in the same transaction as `mark_summarised`.
- The **read side** (`services/views.py`): **`views.list_documents`** returns every
  stored document as the `DocumentView` read model (through the aggregate), and
  **`views.get_document_summary`** serves the summary from the denormalized `summaries`
  store (`GET /api/documents/{id}/summary`, 404 when absent) — both bypass the bus
  (ADR-015/016). The Postgres read model (`PostgresSummaryReadModel`, Core over a
  `summaries` table) is proven end to end in the composition integration test.
- The **serial job queue** (`entrypoints/`): a `JobQueue` drains `DocumentId` intents
  with bounded concurrency, so extraction and summarization (and the podcast ahead) run
  off the request path — `AdvanceDocument` enqueues, and the worker derives the command
  from the document's persisted status via the `NEXT_COMMAND` table, so no handler
  names a stage. Startup `reconcile_unfinished_documents` asks that same table which
  documents a restart left unfinished, with no jobs table. Proven by an integration
  test that uploads a real PDF and polls the live app through to `SUMMARISED`.
- The **composition root** (`entrypoints/`): environment-driven `Settings`, a
  per-process engine wired to the real adapters (the infra seams retired), and a
  `lifespan` that provisions the schema + bucket, builds the process-wide bus, and
  starts the job queue at startup — so `docker compose up` (api + Postgres + MinIO)
  runs the app end to end, proven by an integration test driving the live stack with
  no `dependency_overrides`.
- The **frontends** (the `frontend/` tree): React + TypeScript on Vite, react-router
  splitting two role-based surfaces served by one nginx **`web`** compose service that
  also reverse-proxies same-origin `/api` (a Vite proxy mirrors it in development). The
  **admin console** (`/admin`) uploads, lists — polling the pipeline through TanStack
  Query until every document is terminal — deletes, and inspects the raw extraction. The
  **reader** (`/`) lists the library and reads per-chapter summaries navigated by the
  table of contents (`/api/documents/{id}/chapters`), extracted text staying admin-only.
  Component-tested against a mocked client (Vitest); a CI node job runs its lint /
  typecheck / tests / build, and a CI image-build job builds the api + web images on
  every PR.
- The **E2E suite** (the `e2e/` tree): black-box Playwright specs (`make e2e`) that
  bring up the `docker compose` stack and drive both surfaces through a browser over
  same-origin `/api` — admin (upload → `SUMMARISED` → summary / extracted / PDF /
  delete) and reader (library grid → chapter navigation → per-chapter summary) — with
  the mock summarizer forced for determinism. Run locally with `make e2e` and gated on
  every PR by a dedicated CI job that cold-builds the stack.

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
- [ADR-010 — Composition root: settings, engine lifespan, and startup provisioning](adr/010-composition-root-settings-and-startup-provisioning.md)
- [ADR-011 — Message bus: commands and events through one `bus.handle()`](adr/011-message-bus-commands-and-events.md)
- [ADR-012 — The pipeline as events](adr/012-pipeline-as-events.md)
- [ADR-013 — Serial job queue and restart recovery](adr/013-serial-job-queue-and-restart-recovery.md)
- [ADR-014 — Status-driven pipeline advance](adr/014-status-driven-pipeline-advance.md)
- [ADR-015 — A CQRS read side: reads bypass the bus](adr/015-cqrs-read-side.md)
- [ADR-016 — AI summaries: a pipeline stage and its read model](adr/016-ai-summaries-and-the-summary-read-model.md)
- [ADR-017 — The admin SPA: first frontend and its serving topology](adr/017-admin-spa-first-frontend-and-serving-topology.md)
- [ADR-018 — Real summarizer adapter: OpenAI-compatible, config-selected](adr/018-openai-compatible-summarizer-adapter.md)
- [ADR-019 — Admin content viewers: storage-backed reads](adr/019-admin-content-viewers-and-storage-backed-reads.md)
- [ADR-020 — Map-reduce summarization for oversized documents](adr/020-map-reduce-summarization-for-oversized-documents.md)
- [ADR-021 — Chapters from the PDF table of contents](adr/021-chapters-from-the-pdf-table-of-contents.md)
- [ADR-022 — The reader SPA and the reader/admin role split](adr/022-the-reader-spa-and-the-role-split.md)
- [ADR-023 — Deleting a document mid-pipeline](adr/023-deleting-a-document-mid-pipeline.md)
- [ADR-024 — Alembic migrations replace startup `create_all`](adr/024-alembic-migrations.md)
- [ADR-025 — End-to-end tests with Playwright](adr/025-end-to-end-tests-with-playwright.md)
- [ADR-026 — Documents are classified as Books or Articles](adr/026-document-kind.md)
