# ADR-029: Bounded Retry for Outbound HTTP

**Status:** Accepted

> Applies to the LLM adapters of [ADR-018](018-openai-compatible-summarizer-adapter.md)
> and [ADR-028](028-enrichment-cover-authors-year.md), whose failures the pipeline
> turns into `FAILED` ([ADR-014](014-status-driven-pipeline-advance.md)).

---

## Context

Three calls leave the process over `httpx`: the summarizer's completion, the metadata
inferer's completion, and the cover renderer's image GET. None retried, and httpx's
transport default is `retries=0` — so one 502 from the LLM endpoint raised, the handler
caught it and marked the document `FAILED`, and `FAILED` has no next command (ADR-014).
A single transient blip permanently lost a document.

Every other outbound path already retried from its library: botocore for S3, urllib3
under trafilatura's page fetch. The httpx path was the only one with none.

---

## Decision

**One shared helper, not three loops.** `adapters/http/retry.py` holds `with_retry`,
wrapping any awaited call, plus the `post_json` both LLM adapters use. No new
dependency — tenacity would import a framework to express a policy worth stating
outright.

**Three attempts, exponential backoff, full jitter, capped.** The jitter is not
decoration: without it every caller retries in lockstep and a recovering upstream is
met by a second herd.

**Retry only what a retry can fix** — connection errors, timeouts, 429, and 5xx. Any
other 4xx is the request's own fault and raises on the first attempt. A `Retry-After`
the server names wins over the computed backoff.

**The policy is an injected value with a default.** `RetryPolicy` joins `timeout` and
`transport` as a constructor seam, so tests pin the behaviour without sleeping and no
setting is invented before a deployment needs to move one.

---

## Consequences

- A stage's worst case becomes roughly three times its timeout plus backoff. Queue
  workers are few and fixed at startup (one by default, ADR-013), so that wait is
  head-of-line delay for whatever is queued behind it.
- Map-reduce (ADR-020) retries per chunk, not per document: attempts stay bounded per
  call, but an oversized document has more calls that can spend them.
- The LLM calls are idempotent in effect and not in billing — a retry after a timeout
  can pay twice for one summary. Accepted; the alternative is losing the document.
- The cover download stays best-effort: exhausted attempts return `None` rather than
  raising, so enrichment still completes with `has_cover=False` (ADR-028).
- Retry narrows how often a document reaches `FAILED`; it does not make `FAILED`
  recoverable. A sustained outage, or a bad API key, still lands there terminally —
  the way back out is a separate decision, still open in ADR-002.
