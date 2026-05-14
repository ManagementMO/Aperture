import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";

import { Layout } from "./Layout";
import { Overview } from "./pages/Overview";
import { Reports } from "./pages/Reports";
import { SchemaOverlay } from "./pages/SchemaOverlay";

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
