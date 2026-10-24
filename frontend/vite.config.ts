import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import path from "node:path";

export default defineConfig({
  plugins: [react()],
  resolve: { alias: { "@": path.resolve(__dirname, "src") } },
  server: {
    port: 5173,
    // In dev the API runs on :8000 (uv run evalh serve); in docker nginx does this proxying.
    proxy: { "/api": { target: process.env.API_URL ?? "http://localhost:8000", changeOrigin: true } },
  },
  test: { environment: "node" },
});
