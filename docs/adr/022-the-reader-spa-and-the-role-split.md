# ADR-022: The Reader SPA and the Reader/Admin Role Split

**Status:** Accepted

> The second user-facing surface. Consumes the per-chapter read side of
> [ADR-021](021-chapters-from-the-pdf-table-of-contents.md)/[ADR-016](016-ai-summaries-and-the-summary-read-model.md),
> and takes the reader surface + role split that
> [ADR-017](017-admin-spa-first-frontend-and-serving-topology.md) deferred.

---

## Context

The only surface so far is the admin SPA (ADR-017): upload, list, delete, inspect.
There is no way to *read*. The read side already serves an ordered table of contents
with a per-chapter summary (`GET /documents/{id}/chapters`), but nothing consumes it.
This slice adds the reader — the daily-use surface where the summaries *are* the
product — and, with it, begins the reader/admin split ADR-017 recorded as deferred.

---

## Decision

**A second surface in the same `frontend/` tree, selected by client-side routing.**
Add **react-router**; the reader is the root `/` (the daily read experience), and the
existing admin SPA moves behind `/admin`, otherwise unchanged. One Vite build, one
`web`/nginx service, one CI node job — the split is **by route and role, not by build
artifact**. Routing is app plumbing, distinct from the UI-framework dependency ADR-017
declines to take on (the CSS is still hand-written).

**The reader reads summaries, never extracted text.** The library lists documents; a
document view (`/documents/:id`) navigates chapters — the TOC — and renders the
selected chapter's summary as Markdown. A chapter with no summary yet shows a pending
note, not a broken view. The extracted Markdown and the source PDF stay admin-only
(ADR-019 scope holds — extracted text is reader-invisible).

**nginx already serves a history fallback** (`try_files … /index.html`), so deep links
like `/documents/:id` survive a refresh with no server change.

**Pragmatic testing** (ADR-017 carried over): component tests exercise the flows
against a mocked client; no backend-style red→green ceremony.

---

## Consequences

- The role split is now real but **soft**: one build, a shared client and shared
  types, no auth boundary. A hardened boundary (auth, perhaps a separate deploy) is a
  later decision, taken when the surfaces genuinely diverge; the routes are the seam.
- **react-router** is the first runtime dependency beyond React and Query — justified
  by real, shareable URLs (a link straight to a document, a working back button) over
  a hand-rolled view switch that would re-grow history and deep-linking by hand.
- Reader and admin share the polled-list query idiom (ADR-017); the reader's chapter
  view is a new per-document query, idle once the document is terminal.
- The root surface is now the reader; a reviewer landing on `/` reads, and reaches the
  maintenance console deliberately at `/admin`.
