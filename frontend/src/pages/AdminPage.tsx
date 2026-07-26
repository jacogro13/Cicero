import { DocumentList } from "../components/DocumentList";
import { UploadForm } from "../components/UploadForm";
import styles from "./AdminPage.module.css";

// The maintenance console (ADR-022): upload, list, delete, and inspect the raw
// extraction — the surface a reader never sees.
export function AdminPage() {
  return (
    <div className={styles.page}>
      <section className={styles.section}>
        <UploadForm />
      </section>

      <section className={styles.section}>
        <h2 className={styles.heading}>Documents</h2>
        <DocumentList />
      </section>
    </div>
  );
}
