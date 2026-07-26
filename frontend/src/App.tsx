import { Route, Routes } from "react-router-dom";

import { Layout } from "./components/Layout";
import { AdminPage } from "./pages/AdminPage";
import { LibraryPage } from "./pages/LibraryPage";
import { ReaderPage } from "./pages/ReaderPage";

// The two surfaces split by role (ADR-022): the reader is the root — the daily
// read experience — and the admin console sits behind /admin. One build, one
// client; the split is by route, not by artifact.
export function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<LibraryPage />} />
        <Route path="documents/:id" element={<ReaderPage />} />
        <Route path="admin" element={<AdminPage />} />
      </Route>
    </Routes>
  );
}
