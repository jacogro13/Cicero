import { useQuery } from "@tanstack/react-query";

import { getSummary } from "../api/documents";
import { useResummariseDocument } from "../hooks/useDocumentMutations";
import { MarkdownModal } from "./MarkdownModal";
import styles from "./MarkdownModal.module.css";

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
  const resummarise = useResummariseDocument();

  // The action lives here rather than in the row: it is the summary in front of you
  // that you judge worth redoing, and the row's grid has no free column (ADR-032).
  // Closing is not optional — the summary it is showing is deleted by the click.
  const summariseAgain = () => {
    resummarise.mutate(documentId);
    onClose();
  };

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
      action={
        <button
          className={styles.actionButton}
          onClick={summariseAgain}
          disabled={resummarise.isPending}
        >
          Summarise again
        </button>
      }
    />
  );
}
