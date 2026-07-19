# ADR-014: Status-Driven Pipeline Advance

**Status:** Accepted

> Supersedes the state machine in [ADR-002](002-document-status-state-machine.md)
> (the enum, not its encapsulation rules) and closes the fork left open in
> [ADR-013](013-serial-job-queue-and-restart-recovery.md).

---

## Context

ADR-013 left the edge hardcoded to one job type: the worker turned every intent into
`ExtractDocument`. A second stage (summarization) breaks that — the edge must learn
which command an intent means. ADR-013 named two options and deferred: a kind tag on
the intent, or deriving the command from the document's persisted status.

The tag loses on two counts. It duplicates state the database already holds, so a
stale tag and the status can disagree; and restart recovery, which has no tag to read,
would stay a separate code path rather than collapsing into normal dispatch.

Deriving from status needs a status that actually encodes **pipeline position**.
`READY` today means *extraction done* (ADR-002) — a name that cannot also mean
*summaries done*.

---

## Decision

**`DocumentStatus` names the stage, not readiness.** `PROCESSING → EXTRACTING`,
`READY → EXTRACTED`. Each status answers "what has happened, and therefore what is
next." Every member stays reachable: summarization adds `SUMMARISING`/`SUMMARISED`
when it lands, rather than parking a dead terminal state now. `FAILED` stays single —
which stage failed
is in the logs, and splitting it is speculative until a second stage can fail.

**The edge maps status → next command.** One `NEXT_COMMAND` table in `entrypoints/`
is the only place a stage order is written down; a `None` means the document is
terminal and the intent is dropped. Command origination stays greppable in
`entrypoints/` alone (ADR-012 held without asterisks).

**One `AdvanceDocument` handler replaces `EnqueueExtraction`.** It enqueues
`event.document_id` for any event carrying one, naming no verb. A new stage then costs
one status, one `NEXT_COMMAND` entry, and one subscription — no new handler class.

**Restart recovery is the same path as dispatch.** `reconcile_unfinished_documents`
re-enqueues every document whose status has a next command, so it also recovers the
`UPLOADED`-but-never-enqueued gap ADR-013 listed as a known hole.

---

## Consequences

- The stage order lives in one table, not spread across handlers; reading it is how
  you learn the pipeline.
- Dispatch is idempotent by construction: re-enqueuing an id re-reads the status, so a
  duplicate intent re-runs the current stage (unguarded `mark_*`, ADR-002) or is dropped.
- `EXTRACTING` and `EXTRACTED` are wire-visible — the API status strings changed. No
  deployment carries the old values, so no data migration is written.
- "Readable" is no longer one status but "`EXTRACTED` or later", a predicate that grows
  with the pipeline. Only the read side needs it, so it is not modelled yet.
- An intent enqueued twice for the *same* stage runs it twice. Serial concurrency makes
  interleaving unlikely; a claim/lease is the fix if it ever bites.
