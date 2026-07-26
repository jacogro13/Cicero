import { useState } from "react";
import { Link } from "react-router-dom";

import type { DocumentKind } from "../api/documents";
import { StatusBadge } from "../components/StatusBadge";
import { useDocuments } from "../hooks/useDocuments";
import styles from "./LibraryPage.module.css";

// The reader keeps books and articles in separate grids (ADR-026); the switch
// scopes the library to one kind, defaulting to Books — the primary shelf.
const KINDS: { value: DocumentKind; label: string }[] = [
  { value: "BOOK", label: "Books" },
  { value: "ARTICLE", label: "Articles" },
];

const EMPTY: Record<DocumentKind, string> = {
  BOOK: "No books yet.",
  ARTICLE: "No articles here.",
};

// The reader's front door (ADR-022): every document as a card linking into the
// chapter reader. Status is shown so a document still moving through the pipeline
// reads as pending rather than broken.
export function LibraryPage() {
  const { data, isPending, isError } = useDocuments();
  const [kind, setKind] = useState<DocumentKind>("BOOK");

  if (isPending) {
    return <p className={styles.muted}>Loading library…</p>;
  }
  if (isError) {
    return <p className={styles.error}>Could not load the library.</p>;
  }

  const shown = data.filter((doc) => doc.kind === kind);

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <h1 className={styles.heading}>Library</h1>
        <div className={styles.switch} role="group" aria-label="Document kind">
          {KINDS.map(({ value, label }) => (
            <button
              key={value}
              type="button"
              aria-pressed={kind === value}
              className={kind === value ? styles.tabActive : styles.tab}
              onClick={() => setKind(value)}
            >
              {label}
            </button>
          ))}
        </div>
      </div>
      {shown.length === 0 ? (
        <p className={styles.muted}>{EMPTY[kind]}</p>
      ) : (
        <ul className={styles.grid}>
          {shown.map((doc) => (
            <li key={doc.id}>
              <Link to={`/documents/${doc.id}`} className={styles.card}>
                <span className={styles.title}>{doc.title}</span>
                <StatusBadge status={doc.status} />
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
