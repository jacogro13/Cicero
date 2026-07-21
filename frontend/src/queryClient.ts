import { QueryClient } from "@tanstack/react-query";

// One client for the app. Per-query polling (refetchInterval) is set where it is
// needed — the document list, which polls while any document is still moving
// through the pipeline (ADR-017) — not globally here.
export const queryClient = new QueryClient();
