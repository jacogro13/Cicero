import { useState } from "react";

import {
  fileUrl,
  hasExtractedContent,
  type DocumentKind,
  type DocumentResponse,
} from "../api/documents";
import {
  useDeleteDocument,
  useRetryDocument,
  useSetDocumentKind,
} from "../hooks/useDocumentMutations";
import { ContentPanel } from "./ContentPanel";
import { StatusBadge } from "./StatusBadge";
import { SummaryPanel } from "./SummaryPanel";
import styles from "./DocumentRow.module.css";

const KINDS: { value: DocumentKind; label: string }[] = [
  { value: "BOOK", label: "Book" },
  { value: "ARTICLE", label: "Article" },
];

export function DocumentRow({ doc }: { doc: DocumentResponse }) {
  const del = useDeleteDocument();
  const retry = useRetryDocument();
  const setKind = useSetDocumentKind();
  const [showSummary, setShowSummary] = useState(false);
  const [showContent, setShowContent] = useState(false);

  return (
    <li className={styles.row}>
      <span className={styles.title}>{doc.title}</span>
      {/* Kind is derived from the source at ingest and can be wrong (a paper
          uploaded as a PDF is not a book); correcting it here is the only way to
          move a document to the other reader shelf (ADR-026). */}
      <div
        className={styles.kind}
        role="group"
        aria-label={`Kind of ${doc.title}`}
      >
        {KINDS.map(({ value, label }) => (
          <button
            key={value}
            type="button"
            aria-pressed={doc.kind === value}
            className={
              doc.kind === value ? styles.kindActive : styles.kindOption
            }
            disabled={doc.kind === value || setKind.isPending}
            onClick={() => setKind.mutate({ id: doc.id, kind: value })}
          >
            {label}
          </button>
        ))}
      </div>
      <span className={styles.status}>
        <StatusBadge status={doc.status} />
      </span>
      {doc.status === "SUMMARISED" && (
        <button
          className={`${styles.view} ${styles.summaryAction}`}
          onClick={() => setShowSummary(true)}
        >
          View summary
        </button>
      )}
      {/* Nothing re-drives a failed document on its own (ADR-030), so without this
          button the row is a dead end and the only recovery is delete and re-upload. */}
      {doc.status === "FAILED" && (
        <button
          className={`${styles.view} ${styles.retry} ${styles.retryAction}`}
          onClick={() => retry.mutate(doc.id)}
          disabled={retry.isPending}
        >
          Retry
        </button>
      )}
      {hasExtractedContent(doc) && (
        <button
          className={`${styles.view} ${styles.extractedAction}`}
          onClick={() => setShowContent(true)}
        >
          View extracted
        </button>
      )}
      {doc.source_url ? (
        <a
          className={`${styles.view} ${styles.viewLink} ${styles.sourceAction}`}
          href={doc.source_url}
          target="_blank"
          rel="noopener noreferrer"
        >
          Visit article
        </a>
      ) : (
        <a
          className={`${styles.view} ${styles.viewLink} ${styles.sourceAction}`}
          href={fileUrl(doc.id)}
          target="_blank"
          rel="noopener noreferrer"
        >
          View PDF
        </a>
      )}
      <button
        className={`${styles.delete} ${styles.deleteAction}`}
        onClick={() => del.mutate(doc.id)}
        disabled={del.isPending}
      >
        Delete
      </button>

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
