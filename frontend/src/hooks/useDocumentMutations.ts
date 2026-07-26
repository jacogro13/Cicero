import { useMutation, useQueryClient } from "@tanstack/react-query";

import { deleteDocument, ingestUrl, uploadDocument } from "../api/documents";
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

export function useDeleteDocument() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => deleteDocument(id),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: documentsKey }),
  });
}
