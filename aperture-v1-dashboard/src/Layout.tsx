import type { CSSProperties, ReactNode } from "react";
import { NavLink } from "react-router-dom";

export function Layout({ children }: { children: ReactNode }) {
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
        <NavLink to="/" end style={navStyle}>
          Overview
        </NavLink>
        <NavLink to="/reports" style={navStyle}>
          Reports
        </NavLink>
        <NavLink to="/overlay" style={navStyle}>
          Schema Overlay
        </NavLink>
      </nav>
      <main style={{ padding: 24 }}>{children}</main>
    </div>
  );
}

const navStyle = ({ isActive }: { isActive: boolean }): CSSProperties => ({
  color: isActive ? "var(--accent)" : "var(--muted)",
  textDecoration: "none",
  fontSize: 14,
});
