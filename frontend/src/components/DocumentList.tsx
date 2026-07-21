import { useDocuments } from "../hooks/useDocuments";
import { DocumentRow } from "./DocumentRow";
import styles from "./DocumentList.module.css";

export function DocumentList() {
  const { data, isPending, isError } = useDocuments();

  if (isPending) {
    return <p className={styles.muted}>Loading documents…</p>;
  }
  if (isError) {
    return <p className={styles.error}>Could not load documents.</p>;
  }
  if (data.length === 0) {
    return (
      <p className={styles.muted}>No documents yet — upload one above.</p>
    );
  }

  return (
    <ul className={styles.list}>
      {data.map((doc) => (
        <DocumentRow key={doc.id} doc={doc} />
      ))}
    </ul>
  );
}
