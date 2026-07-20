# ADR-015: A CQRS Read Side — Reads Bypass the Bus

**Status:** Accepted

> Closes the CQRS exit that [ADR-011](011-message-bus-commands-and-events.md) and
> [ADR-012](012-pipeline-as-events.md) left deferred (reads riding the command bus).

---

## Context

Every use case rides the command bus today, reads included: `ListDocuments` is a
`Command`. ADR-011/012 flagged that as a placeholder — a read is not a state change,
so routing it through a command handler (with its throwaway "echo the result" hook)
buys nothing. Cicero is read-heavy by design: the reader experience — summaries, TOC,
notes, chat — *is* the product. Summaries (the next slice) are the first read-shaped
feature, so this is the point of genuine need to split reads out.

---

## Decision

**Reads bypass the bus.** A `services/views.py` module holds query functions that take
a `uow_factory`, open a short read-only transaction, and return **read-shaped DTOs** —
no command, no event, no commit. `GET /documents` calls `views.list_documents`
directly; `commands.ListDocuments` and its handler are **retired**, the trivial proof
that reads are off the bus.

**The DTO is the read contract.** `DocumentView` is separate from the domain
`Document` (so the read shape can diverge from the aggregate) and from the entrypoints
`DocumentResponse` (the wire schema stays HTTP-only; the view is application-layer).
For a list of `id`/`title`/`status` the three shapes still coincide; summaries are
where the view earns its independence.

**Phase the depth.** Adopt *reads-off-the-bus* now — the query still reads through the
aggregate repository (`uow.documents.find_all`). A **denormalized read model maintained
by event handlers** arrives only where a view genuinely needs it (per-document
summaries, next slice), never speculatively for a document list.

---

## Consequences

- The command bus now carries only writes. Its "return the originating command's
  result" deviation (ADR-011) still serves writes that echo a created resource, but no
  read depends on it any more.
- Listing costs two mappings (`Document → DocumentView → DocumentResponse`) — accepted:
  the read/write seam is the point, and summaries make the view diverge from the
  aggregate for real.
- A read opens its own transaction off the `uow_factory`, independent of any preceding
  write — correct for a query, and the route needs the factory injected alongside the
  bus.
- The read still touches the write-side repository (loads aggregates, registers `seen`)
  — a deliberate half-measure. The denormalized projection closes it where a view's
  shape actually departs from the aggregate's.
- No import-linter change: `views.py` sits in `services`, reading the same domain ports
  as the command handlers.
