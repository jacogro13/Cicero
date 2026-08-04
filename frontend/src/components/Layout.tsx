import { NavLink, Outlet, useLocation } from "react-router-dom";

import styles from "./Layout.module.css";

// The shell shared by both surfaces (ADR-022): a brand that returns to the
// library and a nav between the reader and the admin console.
const navClass = ({ isActive }: { isActive: boolean }) =>
  isActive ? `${styles.link} ${styles.active}` : styles.link;

export function Layout() {
  const wide = useLocation().pathname.startsWith("/admin");

  return (
    <div className={wide ? `${styles.shell} ${styles.wide}` : styles.shell}>
      <header className={styles.header}>
        <NavLink to="/" className={styles.brand}>
          Cicero
        </NavLink>
        <nav className={styles.nav}>
          <NavLink to="/" end className={navClass}>
            Library
          </NavLink>
          <NavLink to="/admin" className={navClass}>
            Admin
          </NavLink>
        </nav>
      </header>
      <main className={styles.main}>
        <Outlet />
      </main>
    </div>
  );
}
