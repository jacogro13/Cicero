import { useQuery } from "@tanstack/react-query";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { getSummary } from "../api/documents";
import styles from "./SummaryPanel.module.css";

interface SummaryPanelProps {
  documentId: string;
  title: string;
  onClose: () => void;
}

// Reads the summary off the CQRS read side (GET /documents/{id}/summary,
// ADR-016) on demand and shows it in a modal — the admin's window onto what a
// reader would see.
export function SummaryPanel({ documentId, title, onClose }: SummaryPanelProps) {
  const summary = useQuery({
    queryKey: ["summary", documentId],
    queryFn: () => getSummary(documentId),
  });

  return (
    <div className={styles.overlay} onClick={onClose}>
      <div
        className={styles.panel}
        role="dialog"
        aria-label={`Summary of ${title}`}
        onClick={(event) => event.stopPropagation()}
      >
        <header className={styles.header}>
          <h2 className={styles.title}>{title}</h2>
          <button className={styles.close} onClick={onClose} aria-label="Close">
            ×
          </button>
        </header>

        {summary.isLoading && <p className={styles.muted}>Loading summary…</p>}
        {summary.isError && (
          <p className={styles.error}>Could not load the summary.</p>
        )}
        {summary.data && (
          <div className={styles.markdown}>
            {/* The summary is LLM-authored Markdown; react-markdown renders it to
                elements and drops raw HTML, so the content can't inject markup. */}
            <Markdown remarkPlugins={[remarkGfm]}>{summary.data.text}</Markdown>
          </div>
        )}
      </div>
    </div>
  );
}
