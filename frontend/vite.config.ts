import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// Dev server proxies API + receipt images to the FastAPI backend on :8137,
// so the frontend can call same-origin paths and stay simple.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      "/api": "http://localhost:8137",
      "/receipts": "http://localhost:8137",
    },
  },
});
