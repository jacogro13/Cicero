import { useEffect } from "react";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";

import styles from "./MarkdownModal.module.css";

interface MarkdownModalProps {
  ariaLabel: string;
  title: string;
  onClose: () => void;
  isLoading: boolean;
  isError: boolean;
  loadingLabel: string;
  errorLabel: string;
  markdown?: string;
}

// The shared modal shell for the admin's two Markdown read views — the LLM
// summary and the extracted text. It renders whatever Markdown it is given to
// safe elements (react-markdown drops raw HTML), so neither view can inject
// markup. The query lives with each caller; this component is presentational.
export function MarkdownModal({
  ariaLabel,
  title,
  onClose,
  isLoading,
  isError,
  loadingLabel,
  errorLabel,
  markdown,
}: MarkdownModalProps) {
  // Close on Escape, so a long document never has to be scrolled back to the top
  // to be dismissed (the × in the header stays pinned for the same reason).
  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [onClose]);

  return (
    <div className={styles.overlay} onClick={onClose}>
      <div
        className={styles.panel}
        role="dialog"
        aria-label={ariaLabel}
        onClick={(event) => event.stopPropagation()}
      >
        <header className={styles.header}>
          <h2 className={styles.title}>{title}</h2>
          <button className={styles.close} onClick={onClose} aria-label="Close">
            ×
          </button>
        </header>

        {isLoading && <p className={styles.muted}>{loadingLabel}</p>}
        {isError && <p className={styles.error}>{errorLabel}</p>}
        {markdown !== undefined && (
          <div className={styles.markdown}>
            <Markdown remarkPlugins={[remarkGfm]}>{markdown}</Markdown>
          </div>
        )}
      </div>
    </div>
  );
}
