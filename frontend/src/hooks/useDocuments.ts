import { useQuery } from "@tanstack/react-query";

import { isPending, listDocuments } from "../api/documents";

export const documentsKey = ["documents"] as const;

// The document list, polled while any document is still moving through the
// pipeline and idle once every document is terminal (ADR-017). This is the
// client-side stand-in for the deferred push channel.
export function useDocuments() {
  return useQuery({
    queryKey: documentsKey,
    queryFn: listDocuments,
    refetchInterval: (query) =>
      query.state.data?.some(isPending) ? 1500 : false,
  });
}
