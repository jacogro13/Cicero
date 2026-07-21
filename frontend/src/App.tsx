import { DocumentList } from "./components/DocumentList";
import { UploadForm } from "./components/UploadForm";
import styles from "./App.module.css";

export function App() {
  return (
    <main className={styles.app}>
      <header className={styles.header}>
        <h1 className={styles.title}>Cicero</h1>
        <p className={styles.subtitle}>Admin</p>
      </header>

      <section className={styles.section}>
        <UploadForm />
      </section>

      <section className={styles.section}>
        <h2 className={styles.heading}>Documents</h2>
        <DocumentList />
      </section>
    </main>
  );
}
