import { useRef, useState, type FormEvent } from "react";

import { useUploadDocument } from "../hooks/useDocumentMutations";
import styles from "./UploadForm.module.css";

export function UploadForm() {
  const upload = useUploadDocument();
  const formRef = useRef<HTMLFormElement>(null);
  const [title, setTitle] = useState("");
  const [file, setFile] = useState<File | null>(null);

  const canSubmit = title.trim() !== "" && file !== null && !upload.isPending;

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!file) {
      return;
    }
    upload.mutate(
      { title: title.trim(), file },
      {
        onSuccess: () => {
          setTitle("");
          setFile(null);
          formRef.current?.reset();
        },
      },
    );
  }

  return (
    <form ref={formRef} className={styles.form} onSubmit={handleSubmit}>
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

      <button className={styles.submit} type="submit" disabled={!canSubmit}>
        {upload.isPending ? "Uploading…" : "Upload"}
      </button>

      {upload.isError && (
        <p className={styles.error} role="alert">
          {upload.error.message}
        </p>
      )}
    </form>
  );
}
