import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Routes, Route, NavLink, Navigate } from "react-router-dom";

import { Overview } from "./pages/Overview";
import { Reports } from "./pages/Reports";
import { SchemaOverlay } from "./pages/SchemaOverlay";

function Layout({ children }: { children: React.ReactNode }) {
  return (
    <div style={{ minHeight: "100vh" }}>
      <nav
        style={{
          display: "flex",
          gap: 16,
          padding: "16px 24px",
          borderBottom: "1px solid var(--border)",
          background: "var(--panel)",
        }}
      >
        <strong style={{ marginRight: 24 }}>Aperture v1</strong>
        <NavLink to="/" end style={navStyle}>Overview</NavLink>
        <NavLink to="/reports" style={navStyle}>Reports</NavLink>
        <NavLink to="/overlay" style={navStyle}>Schema Overlay</NavLink>
      </nav>
      <main style={{ padding: 24 }}>{children}</main>
    </div>
  );
}

const navStyle = ({ isActive }: { isActive: boolean }): React.CSSProperties => ({
  color: isActive ? "var(--accent)" : "var(--muted)",
  textDecoration: "none",
  fontSize: 14,
});

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <Layout>
        <Routes>
          <Route path="/" element={<Overview />} />
          <Route path="/reports" element={<Reports />} />
          <Route path="/overlay" element={<SchemaOverlay />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Layout>
    </BrowserRouter>
  </StrictMode>
);
