import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react-swc";
import path from "path";

export default defineConfig({
  plugins: [react()],
  resolve: { alias: { "@": path.resolve(__dirname, "./src") } },
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    // one worker: the build machine runs several sessions and is short on memory
    pool: "threads",
    fileParallelism: false,
    maxWorkers: 1,
    minWorkers: 1,
  },
});
