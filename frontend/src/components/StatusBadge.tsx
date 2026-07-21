import type { DocumentStatus } from "../api/documents";
import styles from "./StatusBadge.module.css";

const LABELS: Record<DocumentStatus, string> = {
  UPLOADED: "Uploaded",
  EXTRACTING: "Extracting",
  EXTRACTED: "Extracted",
  SUMMARISING: "Summarising",
  SUMMARISED: "Summarised",
  FAILED: "Failed",
};

// Statuses where the pipeline is actively working get a pulsing dot; colour is
// driven by the data-status attribute in the stylesheet.
const WORKING: ReadonlySet<DocumentStatus> = new Set([
  "EXTRACTING",
  "SUMMARISING",
]);

export function StatusBadge({ status }: { status: DocumentStatus }) {
  return (
    <span className={styles.badge} data-status={status}>
      {WORKING.has(status) && <span className={styles.dot} aria-hidden />}
      {LABELS[status]}
    </span>
  );
}
