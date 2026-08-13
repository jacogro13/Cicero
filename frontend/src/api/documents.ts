import { http } from "./http";

// Mirrors the backend DocumentStatus enum — the pipeline stage a document has
// reached (ADR-014/016). Forward-only, with FAILED the single terminal.
export type DocumentStatus =
  | "UPLOADED"
  | "EXTRACTING"
  | "EXTRACTED"
  | "SUMMARISING"
  | "SUMMARISED"
  | "FAILED";

// Mirrors the backend DocumentKind enum (ADR-026): a browsing classification the
// reader splits Books | Articles on. Derived from the source at ingest; no
// processing path branches on it.
export type DocumentKind = "BOOK" | "ARTICLE";

export interface DocumentResponse {
  id: string;
  title: string;
  status: DocumentStatus;
  kind: DocumentKind;
  // The link a URL article was ingested from, else null for an uploaded PDF
  // (ADR-027). The backend branches on this, not on kind (which is browsing-only).
  source_url: string | null;
  // Best-effort enrichment (ADR-028), off the readability spine: authors/year are
  // null until inferred, and has_cover is false until a cover has been rendered.
  authors: string | null;
  year: number | null;
  has_cover: boolean;
}

export interface SummaryResponse {
  text: string;
}

// One entry of the reader's table of contents (ADR-021): a chapter's position,
// its title, and its summary — null until the chapter has been summarised.
export interface ChapterResponse {
  index: number;
  title: string;
  summary: string | null;
}

// A document is still moving through the pipeline until it reaches a terminal
// status; the list polls (ADR-017) while any document is pending.
const TERMINAL: ReadonlySet<DocumentStatus> = new Set(["SUMMARISED", "FAILED"]);

export const isPending = (doc: DocumentResponse): boolean =>
  !TERMINAL.has(doc.status);

// The extracted Markdown blob exists once a document reaches EXTRACTED — the
// admin "View extracted" action, mirroring the backend rule (ADR-019).
const EXTRACTED_ONWARD: ReadonlySet<DocumentStatus> = new Set([
  "EXTRACTED",
  "SUMMARISING",
  "SUMMARISED",
]);

export const hasExtractedContent = (doc: DocumentResponse): boolean =>
  EXTRACTED_ONWARD.has(doc.status);

export function listDocuments(): Promise<DocumentResponse[]> {
  return http.get<DocumentResponse[]>("/documents");
}

export function uploadDocument(
  title: string,
  file: File,
): Promise<DocumentResponse> {
  const form = new FormData();
  form.append("title", title);
  form.append("file", file);
  return http.post<DocumentResponse>("/documents", form);
}

// Ingest a web article by URL (ADR-027): no file, the link is the source. The
// document is created as an ARTICLE and enters the same pipeline as an upload.
export function ingestUrl(url: string): Promise<DocumentResponse> {
  return http.postJson<DocumentResponse>("/documents/url", { url });
}

// Correct a misclassified document (ADR-026). The kind is derived from the source
// at ingest, so a journal-article PDF lands as a BOOK; correcting it only moves the
// document to the other shelf — no pipeline stage reads kind.
export function setDocumentKind(
  id: string,
  kind: DocumentKind,
): Promise<DocumentResponse> {
  return http.patchJson<DocumentResponse>(`/documents/${id}`, { kind });
}

// Re-drive a failed document from the start of the pipeline (ADR-030). Nothing
// retries on its own, so this is the only way out of FAILED. 409 if the document is
// not failed — reachable only from a row the poll has not caught up with.
export function retryDocument(id: string): Promise<DocumentResponse> {
  return http.post<DocumentResponse>(`/documents/${id}/retry`);
}

// Throw a document's summaries away and summarise it again (ADR-032). Keeping them
// would make the re-run skip every chapter, so this is the only way to buy new
// summaries after a model or prompt change. 409 unless the document is SUMMARISED.
export function resummariseDocument(id: string): Promise<DocumentResponse> {
  return http.post<DocumentResponse>(`/documents/${id}/resummarise`);
}

export function deleteDocument(id: string): Promise<void> {
  return http.delete(`/documents/${id}`);
}

export function getSummary(id: string): Promise<SummaryResponse> {
  return http.get<SummaryResponse>(`/documents/${id}/summary`);
}

// The reader's table of contents with per-chapter summaries (ADR-021).
export function getChapters(id: string): Promise<ChapterResponse[]> {
  return http.get<ChapterResponse[]>(`/documents/${id}/chapters`);
}

// The extracted Markdown, served raw as text/markdown (ADR-019).
export function getContent(id: string): Promise<string> {
  return http.getText(`/documents/${id}/content`);
}

// The original PDF is streamed as application/pdf; a plain link opens it in the
// browser's native viewer, so this returns the full same-origin URL (with the
// /api prefix the http wrapper otherwise adds).
export function fileUrl(id: string): string {
  return `/api/documents/${id}/file`;
}

// The rendered cover image, served with its sniffed content type (ADR-028). A plain
// same-origin URL for an <img> src; the endpoint 404s until a cover exists, so callers
// gate on has_cover before pointing an <img> at it.
export function coverUrl(id: string): string {
  return `/api/documents/${id}/cover`;
}
