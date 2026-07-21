import styles from "./App.module.css";

// Toolchain shell only. Upload · list · delete · status-poll land in the next
// slice, consuming the read side over same-origin /api (ADR-017).
export function App() {
  return (
    <main className={styles.app}>
      <header className={styles.header}>
        <h1 className={styles.title}>Cicero</h1>
        <p className={styles.subtitle}>Admin</p>
      </header>
    </main>
  );
}
