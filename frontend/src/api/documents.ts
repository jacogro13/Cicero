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

export interface DocumentResponse {
  id: string;
  title: string;
  status: DocumentStatus;
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
