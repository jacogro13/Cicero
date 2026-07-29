import { useState } from "react";

import {
  fileUrl,
  hasExtractedContent,
  type DocumentResponse,
} from "../api/documents";
import { useDeleteDocument } from "../hooks/useDocumentMutations";
import { ContentPanel } from "./ContentPanel";
import { StatusBadge } from "./StatusBadge";
import { SummaryPanel } from "./SummaryPanel";
import styles from "./DocumentRow.module.css";

export function DocumentRow({ doc }: { doc: DocumentResponse }) {
  const del = useDeleteDocument();
  const [showSummary, setShowSummary] = useState(false);
  const [showContent, setShowContent] = useState(false);

  return (
    <li className={styles.row}>
      <span className={styles.title}>{doc.title}</span>
      <StatusBadge status={doc.status} />
      <div className={styles.actions}>
        {doc.status === "SUMMARISED" && (
          <button className={styles.view} onClick={() => setShowSummary(true)}>
            View summary
          </button>
        )}
        {hasExtractedContent(doc) && (
          <button className={styles.view} onClick={() => setShowContent(true)}>
            View extracted
          </button>
        )}
        {doc.source_url ? (
          <a
            className={`${styles.view} ${styles.viewLink}`}
            href={doc.source_url}
            target="_blank"
            rel="noopener noreferrer"
          >
            Visit article
          </a>
        ) : (
          <a
            className={`${styles.view} ${styles.viewLink}`}
            href={fileUrl(doc.id)}
            target="_blank"
            rel="noopener noreferrer"
          >
            View PDF
          </a>
        )}
        <button
          className={styles.delete}
          onClick={() => del.mutate(doc.id)}
          disabled={del.isPending}
        >
          Delete
        </button>
      </div>

      {showSummary && (
        <SummaryPanel
          documentId={doc.id}
          title={doc.title}
          onClose={() => setShowSummary(false)}
        />
      )}
      {showContent && (
        <ContentPanel
          documentId={doc.id}
          title={doc.title}
          onClose={() => setShowContent(false)}
        />
      )}
    </li>
  );
}
