import { Link } from "react-router-dom";

import { StatusBadge } from "../components/StatusBadge";
import { useDocuments } from "../hooks/useDocuments";
import styles from "./LibraryPage.module.css";

// The reader's front door (ADR-022): every document as a card linking into the
// chapter reader. Status is shown so a document still moving through the pipeline
// reads as pending rather than broken.
export function LibraryPage() {
  const { data, isPending, isError } = useDocuments();

  if (isPending) {
    return <p className={styles.muted}>Loading library…</p>;
  }
  if (isError) {
    return <p className={styles.error}>Could not load the library.</p>;
  }
  if (data.length === 0) {
    return <p className={styles.muted}>The library is empty.</p>;
  }

  return (
    <div className={styles.page}>
      <h1 className={styles.heading}>Library</h1>
      <ul className={styles.grid}>
        {data.map((doc) => (
          <li key={doc.id}>
            <Link to={`/documents/${doc.id}`} className={styles.card}>
              <span className={styles.title}>{doc.title}</span>
              <StatusBadge status={doc.status} />
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
