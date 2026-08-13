import { useMutation, useQueryClient } from "@tanstack/react-query";

import {
  deleteDocument,
  ingestUrl,
  resummariseDocument,
  retryDocument,
  setDocumentKind,
  uploadDocument,
  type DocumentKind,
} from "../api/documents";
import { documentsKey } from "./useDocuments";

// Upload a document, then invalidate the list so it refetches and starts
// polling the new document through the pipeline.
export function useUploadDocument() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ title, file }: { title: string; file: File }) =>
      uploadDocument(title, file),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: documentsKey }),
  });
}

// Ingest a web article by URL, then invalidate the list like an upload — the new
// ARTICLE polls through the same pipeline (ADR-027).
export function useIngestUrl() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (url: string) => ingestUrl(url),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: documentsKey }),
  });
}

// Correct a document's browsing kind (ADR-026); the list refetches so the row
// reflects the stored kind rather than a locally assumed one.
export function useSetDocumentKind() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, kind }: { id: string; kind: DocumentKind }) =>
      setDocumentKind(id, kind),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: documentsKey }),
  });
}

// Re-drive a failed document (ADR-030). Invalidating the list is what restarts the
// polling: the document is back at UPLOADED, so isPending holds again and the row
// follows the re-run through the stages on its own.
export function useRetryDocument() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => retryDocument(id),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: documentsKey }),
  });
}

// Summarise a document again from scratch (ADR-032). Like retry, invalidating the list
// is what restarts the polling: the document is back at EXTRACTED, so the row follows
// the new run through SUMMARISING on its own.
export function useResummariseDocument() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => resummariseDocument(id),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: documentsKey }),
  });
}

export function useDeleteDocument() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => deleteDocument(id),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: documentsKey }),
  });
}
