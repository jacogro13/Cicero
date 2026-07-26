import type { DocumentStatus } from "../api/documents";
import styles from "./StatusBadge.module.css";

const LABELS: Record<DocumentStatus, string> = {
  // "Queued", not the raw stage name: the pipeline is serial, so a document that has
  // finished one stage waits its turn for the next behind whatever the single worker
  // is currently processing. The qualifier names the stage it is waiting for.
  UPLOADED: "Queued · extract",
  EXTRACTING: "Extracting",
  EXTRACTED: "Queued · summary",
  SUMMARISING: "Summarising",
  SUMMARISED: "Summarised",
  FAILED: "Failed",
};

// Hover text names *which* stage the document is waiting for, so two "Queued" badges
// are still distinguishable — and a queued document never reads as a stall.
const TITLES: Record<DocumentStatus, string> = {
  UPLOADED: "Queued — waiting to be extracted",
  EXTRACTING: "Extracting the document",
  EXTRACTED: "Queued — waiting to be summarised",
  SUMMARISING: "Summarising the document",
  SUMMARISED: "Ready to read",
  FAILED: "Processing failed",
};

// Statuses where the pipeline is actively working get a pulsing dot; colour is
// driven by the data-status attribute in the stylesheet.
const WORKING: ReadonlySet<DocumentStatus> = new Set([
  "EXTRACTING",
  "SUMMARISING",
]);

export function StatusBadge({ status }: { status: DocumentStatus }) {
  return (
    <span className={styles.badge} data-status={status} title={TITLES[status]}>
      {WORKING.has(status) && <span className={styles.dot} aria-hidden />}
      {LABELS[status]}
    </span>
  );
}
