# ADR-004: Object-Storage Port and the Services Layer

**Status:** Accepted

> Builds on the hexagonal layering of [ADR-001](001-hexagonal-ddd-layering.md)
> and the Unit of Work / repository ports of [ADR-003](003-unit-of-work-and-repository-ports.md):
> the `DocumentStorage` port defined here lives in `domain/` alongside
> `DocumentRepository`, the new **services** layer sits between the domain and
> the outer layers, and the adapter that will back the port (object storage)
> depends inward on the interface, never the reverse.

---

## Context

So far the application has a pure `Document` aggregate ([ADR-001](001-hexagonal-ddd-layering.md),
[ADR-002](002-document-status-state-machine.md)) and the ability to save and
fetch it through a Unit of Work ([ADR-003](003-unit-of-work-and-repository-ports.md)).
The first thing a user actually does is **upload a document**, which has two
distinct effects that must be coordinated:

1. the **file bytes** (the source PDF) have to be put in object storage — they
   are too large for the database and are served back to the reader later as the
   original document; and
2. the **document metadata** (`Document`) has to be persisted so the document
   exists in the library and can be listed, extracted, and summarised.

Two questions follow:

1. **Where does this orchestration live?** It is not domain logic (it touches
   infrastructure — storage and the database) and it is not a transport concern
   (it must work the same whether driven by HTTP, a CLI, or a test). It is a
   **use case**.
2. **How does the use case reach object storage** without depending on a
   concrete S3 client, keeping the domain and the use case infrastructure-
   agnostic (ADR-001)?

The naive alternative — putting upload logic in the HTTP route and calling an S3
SDK directly — couples the transport layer to the database and to a storage
vendor, and leaves no infrastructure-free seam to test the behaviour. ADR-001's
layering exists to prevent exactly this.

---

## Decision

**Introduce the `services/` layer.** Use cases are plain classes under
`services/<aggregate>/`, one per command. They orchestrate the domain and its
ports; they sit between `domain/` (which they may import) and the outer layers
(`entrypoints/`, and later `adapters/`, which import *them*). The hexagonal
chain is now `domain ← services ← entrypoints/adapters` — outer imports inner
only.

**Add a `DocumentStorage` port** (`domain/document/ports/`) — object-storage
operations for a document's files. Like `DocumentRepository` it is per-aggregate
(prefixed, under the aggregate) and collection-like, not a vendor client. It
ships with only what this batch needs:

```python
async def put(self, key: str, data: bytes) -> None: ...
```

`get` / `delete` are added in the batches that need them (serving the original
file, deleting a document) — same just-in-time rule the repository follows.

**Add the `UploadDocument` use case** (`services/document/`). Its dependencies
are constructor parameters — a `uow_factory` and a `DocumentStorage` — never
globals (ADR-001/003):

```python
class UploadDocument:
    def __init__(self, uow_factory: UnitOfWorkFactory, storage: DocumentStorage) -> None: ...
    async def execute(self, title: str, content: bytes) -> Document: ...
```

`execute` creates the `Document`, stores the bytes, persists the metadata in a
Unit of Work, and returns the document. (No `content_type` yet — it is only
needed when the stored file is served back, so it arrives in that batch.)

**The document owns its source-file layout.** A `Document` exposes a derived

```python
@property
def source_key(self) -> str:        # "documents/{id}/source"
```

computed from its identity. This adds no mutable state and no new lifecycle
transition (ADR-002): the location of a document's source file is a pure
function of *which* document it is. The use case stores the bytes at
`document.source_key`; anything that later needs the file derives the same key
from the same document. This is distinct from `content_key`, which locates the
**extracted text** and is set only when the document becomes `READY`.

```mermaid
sequenceDiagram
    participant C as Caller (HTTP route, test, …)
    participant U as UploadDocument
    participant S as DocumentStorage
    participant W as UnitOfWork
    C->>U: await execute(title, content)
    U->>U: doc = Document.create(title)
    U->>S: await storage.put(doc.source_key, content)
    U->>W: async with uow_factory() as uow
    U->>W: await uow.documents.save(doc); await uow.commit()
    U-->>C: return doc
```

**Storage first, then metadata.** The file is put in storage *before* the
document row is committed. The two effects are not in one transaction (object
storage is not transactional with the database), so one ordering must be chosen.
An **orphaned blob** — a stored file with no document pointing at it — is
harmless and trivially garbage-collected; a **dangling pointer** — a committed
document whose file is missing — is a user-visible "open original" failure. So
if storage fails the use case raises and **no document is persisted**; the worst
residue of any failure is a stray blob, never a broken record.

**Upload leaves the document `UPLOADED`.** Upload only receives the source; it
does not start extraction, so the status stays `UPLOADED` (ADR-002). The
transition to `PROCESSING` and the enqueueing of work belong to the batch that
introduces the job queue, not here.

**Extend the architecture fitness function.** The import-linter contract is
grown to the full chain — `domain` must not import `services` or `entrypoints`,
and `services` must not import `entrypoints` — so the new layer is enforced in
CI, not just documented.

**Adapters are still introduced just in time.** This batch ships only an
**in-memory** `DocumentStorage` test double (a dict keyed by storage key),
mirroring the in-memory repository of ADR-003. A real object-storage adapter
(S3-compatible) lands in a later batch behind the *same* port; the upload
behaviour pinned here is re-run against it unchanged. Until that adapter exists
there is no `adapters/` layer to add to the contract.

---

## Consequences

**Benefits:**

- Upload behaviour is captured once, in an infrastructure-free use case that is
  driven the same way from a unit test, an HTTP route, or a CLI. The transport
  layer shrinks to "parse the request, call the use case".
- The domain and services depend only on abstract ports, so both the database
  (ADR-003) and object storage are swappable adapters; the same tests verify the
  behaviour against the in-memory doubles now and the real backends later.
- The storage-first ordering makes the failure mode explicit and benign: a crash
  during upload can leave a stray blob but never a document that fails to open.
- The `source_key` derivation keeps the file's location a function of identity —
  no extra column, no risk of a document and its file disagreeing on where the
  file lives.
- The layering rule is now machine-checked for `services/`, not just `domain/`.

**Costs:**

- Another layer of indirection: a route can no longer "just upload to S3"; it
  goes through a use case and a port. This is the ADR-001 layering tax, paid
  again so the behaviour is testable and the vendor swappable.
- The file write and the metadata commit are not atomic. We accept eventual
  orphaned blobs (cleaned up out of band) as the price of not coupling object
  storage into the database transaction; the ordering guarantees the *safe*
  direction of inconsistency.
- `source_key` fixes a storage-key scheme in the domain. Changing it later means
  a migration of stored objects — acceptable for a scheme this simple, and the
  single source of truth keeps the cost contained.
