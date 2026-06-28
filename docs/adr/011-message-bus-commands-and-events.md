# ADR-011: Message Bus — Commands and Events Through One `bus.handle()`

**Status:** Accepted

---

## Context

The pipeline ahead — upload *causes* extraction, extraction *causes* summarization,
an article *causes* a podcast — is a chain of reactions, not a straight call stack.
Today routes call use cases directly; wiring each new reaction in by hand would
couple producers to consumers. The bus is introduced now, alongside the background
job queue that first needs it, rather than speculatively earlier.

---

## Decision

**Messages are pure data in the domain.** A `Command` is an imperative request
handled by **exactly one** handler; an `Event` is a past-tense fact handled by
**zero or more**. Bases live in `domain/messages.py`; per-aggregate messages in
`domain/<agg>/commands.py` + `events.py` (mirroring the per-aggregate ports/exceptions
split). No dependencies → import-linter contract unchanged.

**The aggregate is the event source.** `Document` gains an `events` list and records
facts off its own lifecycle — `create()` → `DocumentUploaded`; later status methods
raise events as their consumers arrive. `events` is **unmapped and lazily created**
so ORM-loaded instances (built without `__init__`) work, and is **excluded from
equality**, so persisted-vs-loaded comparison is unaffected.

**The Unit of Work collects events.** `collect_new_events()` drains events off the
aggregates the repository has **seen** (each repo tracks a `seen` set, registered on
`save`/`find`). Collection rides the transaction boundary — the same UoW that commits
the state change surfaces the facts it caused.

**The `MessageBus` (`services/`) has one entry point, `handle()`.** It opens a UoW
from the factory, dispatches the message (command → its one handler; event → each
handler), then drains the UoW's new events and keeps going until the queue empties.
**Handlers stay class-based use cases**, callable as `(message, uow)` (via `__call__`);
the **composition root bootstraps** them — injecting deps and building the command/event
maps — and hands the bus to the routes (retiring the per-use-case `Depends` providers).

**Introduced incrementally:** first **`UploadDocument` alone** is refactored through
the bus as proof (pure architecture, no new feature); then the extraction pipeline
becomes events; then the async job-queue transport and restart recovery follow.

---

## Consequences

- Added indirection, plus refactoring the existing use cases into command handlers
  (behavior/tests unchanged, call-shape/DI changed) — justified by making summaries
  and the podcast cheap event handlers instead of fresh wiring each time.
- `handle()` returns the **originating** command's result (cascaded commands' results
  stay internal) so HTTP routes can echo the created resource. This is a deliberate
  intermediate: the clean end-state is CQRS — commands return nothing, reads are
  explicit queries — which is the exit once a real read side exists.
- The bus owns the UoW for a `handle()` call: the command is the first message and
  enters the UoW, so `seen` is populated before the first `collect_new_events()`.
