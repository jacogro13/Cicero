# ADR-007: S3-Compatible Object-Storage Adapter (boto3 in an anyio thread pool)

**Status:** Accepted

> Builds on [ADR-001](001-hexagonal-ddd-layering.md) (layering),
> [ADR-004](004-object-storage-port-and-services-layer.md) (the `DocumentStorage`
> port + storage-first upload), and [ADR-006](006-postgres-persistence-adapter.md)
> (the `adapters/` layer + the testcontainers integration pattern). The port
> shipped with only an in-memory double and the promise of a real adapter — this
> honours it, the storage twin of ADR-006.

---

## Context

`DocumentStorage` exists but only the in-memory double implements it; no bytes are
stored for real. Standing up an S3 client raises three questions: which client and
how to call it from an `async` use case without blocking the event loop, where the
adapter lives, and how it is tested for real rather than mocked.

---

## Decision

**`S3DocumentStorage` in `adapters/storage/`**, implementing `DocumentStorage.put`
against any **S3-compatible** store (Garage / MinIO / AWS) — endpoint-agnostic, not
Garage-specific, so the self-contained stack and a cloud bucket are the same code.
The `adapters/` layer is unchanged structurally, so the import-linter contract is too.

**boto3 (synchronous) offloaded to the anyio worker thread** (`anyio.to_thread.run_sync`)
rather than an async client (aioboto3). botocore is the reference SDK and is sync;
wrapping each call in the thread pool keeps the loop free without adopting aioboto3's
heavier, less-maintained stack. The discipline: **no boto3 call runs un-offloaded on
an async path.**

**The adapter assumes its bucket exists** (provisioned by the compose init /
composition root), exactly as the Postgres adapter assumes its schema does — bucket
lifecycle is a data-plane client's concern to stay out of. Config (endpoint, keys,
bucket, region) arrives as constructor params; live wiring is deferred to the
composition-root slice alongside Postgres.

**`put` only** — the port's surface. No `content_type` yet (ADR-004 defers it until
the file is served back); `get` / `delete` arrive with the slices that need them.

**Tested against a real MinIO testcontainer** in `tests/integration/`, mirroring
ADR-006: a fresh bucket per test for isolation, the round-trip proven by reading the
object back through a separate client.

---

## Consequences

- One `DocumentStorage` contract now holds both in-memory and on a real S3 store —
  proven over the wire, not mocked.
- The integration layer now needs two infra dependencies (Postgres + MinIO), both on
  Docker, both under `make integration`.
- Each call costs a thread hop — negligible against network I/O, and the price of a
  responsive loop; forgetting the offload (calling boto3 directly) is the real hazard.
