import { useQuery } from "@tanstack/react-query";

import { getSummary } from "../api/documents";
import { MarkdownModal } from "./MarkdownModal";

interface SummaryPanelProps {
  documentId: string;
  title: string;
  onClose: () => void;
}

// Reads the summary off the CQRS read side (GET /documents/{id}/summary,
// ADR-016) on demand and shows it in the shared Markdown modal — the admin's
// window onto what a reader would see.
export function SummaryPanel({ documentId, title, onClose }: SummaryPanelProps) {
  const summary = useQuery({
    queryKey: ["summary", documentId],
    queryFn: () => getSummary(documentId),
  });

  return (
    <MarkdownModal
      ariaLabel={`Summary of ${title}`}
      title={title}
      onClose={onClose}
      isLoading={summary.isLoading}
      isError={summary.isError}
      loadingLabel="Loading summary…"
      errorLabel="Could not load the summary."
      markdown={summary.data?.text}
    />
  );
}
