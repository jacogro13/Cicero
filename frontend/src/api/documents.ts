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

// A document is still moving through the pipeline until it reaches a terminal
// status; the list polls (ADR-017) while any document is pending.
const TERMINAL: ReadonlySet<DocumentStatus> = new Set(["SUMMARISED", "FAILED"]);

export const isPending = (doc: DocumentResponse): boolean =>
  !TERMINAL.has(doc.status);

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
