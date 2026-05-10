import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Aperture v1 dashboard. Reads /api/v3.1/* from the FastAPI backend
// (aperture/observability/api_endpoints.py). Backend default port is 8002
// when run via `uvicorn aperture.observability.api_endpoints:create_api_app
//                --factory --host 0.0.0.0 --port 8002`.

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5180,
    proxy: {
      "/api/v3.1": {
        target: process.env.APERTURE_V1_BACKEND ?? "http://127.0.0.1:8002",
        changeOrigin: true,
      },
    },
  },
});
