# ADR-002: Document Status as a Guarded State Machine

**Status:** Accepted

> Builds on the domain layering of [ADR-001](001-hexagonal-ddd-layering.md):
> the state machine lives entirely in the `Document` aggregate root, with no
> infrastructure dependencies.

---

## Context

A document moves through a fixed lifecycle: it is created, sent to extraction,
and ends up either readable or failed. The status must change in the right
order — a document cannot be marked ready before extraction runs, and
re-marking a ready document as processing would be a bug, not a feature.

The simplest implementation would expose `status` as a plain mutable field on
the `Document` dataclass and let callers assign it freely. That is easy to write
but unsafe: any layer could set any status without the entity knowing, and the
invariant that a content key must be present once a document is READY would have
to be enforced somewhere outside the entity that owns it.

Because `Document` is the aggregate root (ADR-001), it is the right place to own
these rules: every status change should go through it.

---

## Decision

Model the lifecycle as four states in a `DocumentStatus` enum:

```
UPLOADED → PROCESSING → READY
UPLOADED → PROCESSING → FAILED
```

A new document starts in `UPLOADED`. Status transitions are encapsulated in
three mutation methods on the `Document` entity — there is no public, freely
assignable `status` setter:

- `mark_processing()` — transition to PROCESSING.
- `mark_ready(content_key: str)` — transition to READY **and** set the
  `content_key` field in the same call.
- `mark_failed()` — transition to FAILED.

`content_key` is an **opaque locator for the document's extracted text** — the
text pulled out of the source when extraction runs. That text is internal raw
material (it feeds AI summary generation; it is *not* shown to the reader, who
reads the summaries and opens the original source for the full text), but the
domain holds the key as a plain string and deliberately does **not** decide or
know what format the text is in, where it physically lives, or how it is produced
or consumed. Those are separate decisions, each documented in its own ADR when
the relevant slice is built (extraction; content storage; summarization).
Keeping the key opaque here is exactly what lets the domain stay
infrastructure-agnostic per ADR-001 — the entity knows *that* there is a content
locator, not *what* or *where*. It is `None` until the document is READY.

There are no reverse transitions. Re-extraction (READY → PROCESSING or
FAILED → PROCESSING) is not supported.

---

## Consequences

**Benefits:**

- `mark_ready()` enforces the invariant that `content_key` is always set when
  the status is READY — the field and the status change atomically in one call,
  so there is no window in which a READY document has a null content key.
- All valid status values and their meaning live in one place, `DocumentStatus`.
  An unknown status string (e.g. from a future persistence layer) fails to
  deserialise rather than flowing through silently.
- The permitted transitions are self-documenting: adding a new one requires a
  deliberate new method, not an ad-hoc assignment at some call site.

**Costs:**

- Re-extraction (retrying a FAILED document) would require a new method
  (e.g. `mark_processing_from_failed()`) and a change to the extraction use
  case. The current design makes that a visible, intentional addition rather
  than an accidental assignment.
- The methods do not guard against illegal call *order* (e.g. `mark_ready()` on
  an already-READY document). The current code never does this; the guard is the
  encapsulation (no raw setter), not runtime state-checking. If a caller ever
  needs that protection, the method is the correct place to add it.

The re-extraction restriction is accepted for now: the project has no
retry-from-failure requirement yet. When it gains one, this ADR is revisited and
the transition is added deliberately.
