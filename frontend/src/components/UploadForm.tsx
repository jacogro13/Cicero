import { useRef, useState, type FormEvent } from "react";

import { useIngestUrl, useUploadDocument } from "../hooks/useDocumentMutations";
import styles from "./UploadForm.module.css";

type Source = "file" | "url";

// The admin ingest console (ADR-022/031): upload a PDF, or ingest a web article by
// URL (ADR-027). A URL always enters as an ARTICLE; the kind can be corrected later.
export function UploadForm() {
  const upload = useUploadDocument();
  const ingest = useIngestUrl();
  const formRef = useRef<HTMLFormElement>(null);
  const [source, setSource] = useState<Source>("file");
  const [title, setTitle] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [url, setUrl] = useState("");

  const busy = upload.isPending || ingest.isPending;
  const canSubmit =
    source === "file"
      ? title.trim() !== "" && file !== null && !busy
      : url.trim() !== "" && !busy;
  const failure = upload.error ?? ingest.error;

  function reset() {
    setTitle("");
    setFile(null);
    setUrl("");
    formRef.current?.reset();
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (source === "file") {
      if (title.trim() === "" || !file) {
        return;
      }
      upload.mutate({ title: title.trim(), file }, { onSuccess: reset });
    } else {
      if (url.trim() === "") {
        return;
      }
      ingest.mutate(url.trim(), { onSuccess: reset });
    }
  }

  return (
    <form ref={formRef} className={styles.form} onSubmit={handleSubmit}>
      <div className={styles.switch} role="group" aria-label="Source">
        {(["file", "url"] as const).map((value) => (
          <button
            key={value}
            type="button"
            aria-pressed={source === value}
            className={source === value ? styles.tabActive : styles.tab}
            onClick={() => setSource(value)}
          >
            {value === "file" ? "File" : "URL"}
          </button>
        ))}
      </div>

      {source === "file" ? (
        <>
          <div className={styles.field}>
            <label className={styles.label} htmlFor="title">
              Title
            </label>
            <input
              id="title"
              className={styles.input}
              type="text"
              value={title}
              placeholder="A name for the document"
              onChange={(event) => setTitle(event.target.value)}
            />
          </div>

          <div className={styles.field}>
            <label className={styles.label} htmlFor="file">
              PDF
            </label>
            <input
              id="file"
              className={styles.file}
              type="file"
              accept="application/pdf"
              onChange={(event) => setFile(event.target.files?.[0] ?? null)}
            />
          </div>
        </>
      ) : (
        <div className={styles.field}>
          <label className={styles.label} htmlFor="url">
            URL
          </label>
          <input
            id="url"
            className={styles.input}
            type="url"
            value={url}
            placeholder="https://example.com/article"
            onChange={(event) => setUrl(event.target.value)}
          />
        </div>
      )}

      <button className={styles.submit} type="submit" disabled={!canSubmit}>
        {source === "file"
          ? upload.isPending
            ? "Uploading…"
            : "Upload"
          : ingest.isPending
            ? "Ingesting…"
            : "Ingest"}
      </button>

      {failure && (
        <p className={styles.error} role="alert">
          {failure.message}
        </p>
      )}
    </form>
  );
}
