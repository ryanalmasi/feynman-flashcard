import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: { host: "localhost", port: 5173, strictPort: true },
  test: {
    environment: "jsdom",
    setupFiles: ["src/test/setup.ts"],
    env: { VITE_API_BASE_URL: "http://api.test" },
  },
});
