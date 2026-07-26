import { useQuery } from "@tanstack/react-query";

import { getChapters } from "../api/documents";

export const chaptersKey = (id: string) => ["chapters", id] as const;

// A document's table of contents with per-chapter summaries (ADR-021), polled
// while any chapter is still awaiting its summary and idle once all are filled —
// the reader's client-side stand-in for the deferred push channel (ADR-017).
export function useChapters(id: string) {
  return useQuery({
    queryKey: chaptersKey(id),
    queryFn: () => getChapters(id),
    refetchInterval: (query) =>
      query.state.data?.some((chapter) => chapter.summary === null)
        ? 1500
        : false,
  });
}
