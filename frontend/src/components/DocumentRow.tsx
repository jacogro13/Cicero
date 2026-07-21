import { useState } from "react";

import type { DocumentResponse } from "../api/documents";
import { useDeleteDocument } from "../hooks/useDocumentMutations";
import { StatusBadge } from "./StatusBadge";
import { SummaryPanel } from "./SummaryPanel";
import styles from "./DocumentRow.module.css";

export function DocumentRow({ doc }: { doc: DocumentResponse }) {
  const del = useDeleteDocument();
  const [showSummary, setShowSummary] = useState(false);

  return (
    <li className={styles.row}>
      <span className={styles.title}>{doc.title}</span>
      <StatusBadge status={doc.status} />
      <div className={styles.actions}>
        {doc.status === "SUMMARISED" && (
          <button
            className={styles.view}
            onClick={() => setShowSummary(true)}
          >
            View summary
          </button>
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
    </li>
  );
}
