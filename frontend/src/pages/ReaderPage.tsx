import { useState } from "react";
import Markdown from "react-markdown";
import { Link, useParams } from "react-router-dom";
import remarkGfm from "remark-gfm";

import { useChapters } from "../hooks/useChapters";
import { useDocuments } from "../hooks/useDocuments";
import styles from "./ReaderPage.module.css";

// The read experience (ADR-022): navigate a document's chapters by its table of
// contents and read the per-chapter summary. Extracted text is never shown here —
// that stays admin-only (ADR-019).
export function ReaderPage() {
  const { id = "" } = useParams();
  const chapters = useChapters(id);
  const documents = useDocuments();
  const title =
    documents.data?.find((doc) => doc.id === id)?.title ?? "Document";
  const [selected, setSelected] = useState(0);

  return (
    <div className={styles.page}>
      <Link to="/" className={styles.back}>
        ← Library
      </Link>
      <h1 className={styles.title}>{title}</h1>
      {renderBody()}
    </div>
  );

  function renderBody() {
    if (chapters.isPending) {
      return <p className={styles.muted}>Loading…</p>;
    }
    if (chapters.isError) {
      return <p className={styles.error}>Could not load this document.</p>;
    }
    if (chapters.data.length === 0) {
      return (
        <p className={styles.muted}>
          This document isn’t ready to read yet.
        </p>
      );
    }

    const active = chapters.data[selected] ?? chapters.data[0];
    return (
      <div className={styles.reader}>
        <nav className={styles.toc} aria-label="Table of contents">
          <ol className={styles.tocList}>
            {chapters.data.map((chapter, index) => (
              <li key={chapter.index}>
                <button
                  className={
                    index === selected
                      ? `${styles.tocItem} ${styles.tocActive}`
                      : styles.tocItem
                  }
                  aria-current={index === selected ? "true" : undefined}
                  onClick={() => setSelected(index)}
                >
                  {chapter.title}
                </button>
              </li>
            ))}
          </ol>
        </nav>
        <article className={styles.summary}>
          <h2 className={styles.chapterTitle}>{active.title}</h2>
          {active.summary === null ? (
            <p className={styles.muted}>
              This chapter hasn’t been summarised yet.
            </p>
          ) : (
            <div className={styles.prose}>
              <Markdown remarkPlugins={[remarkGfm]}>{active.summary}</Markdown>
            </div>
          )}
        </article>
      </div>
    );
  }
}
