/// <reference types="vitest" />
import { defineConfig, type HmrContext, type PluginOption } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { tanstackRouter } from "@tanstack/router-plugin/vite";
import path from "node:path";

const port = Number(process.env.VITE_PORT ?? "5173");
const apiTarget = process.env.VITE_API_PROXY_TARGET ?? "http://localhost:8000";

function routeFullReloadPlugin(): PluginOption {
  return {
    name: "route-full-reload",
    handleHotUpdate({ file, server }: HmrContext) {
      const normalizedFile = file.replaceAll("\\", "/");
      if (
        normalizedFile.includes("/src/routes/") ||
        normalizedFile.endsWith("/src/routeTree.gen.ts")
      ) {
        server.ws.send({ type: "full-reload", path: "*" });
        return [];
      }
      return undefined;
    },
  };
}

export default defineConfig({
  plugins: [
    routeFullReloadPlugin(),
    tanstackRouter({ quoteStyle: "double" }),
    react(),
    tailwindcss(),
  ],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    host: "0.0.0.0",
    port,
    allowedHosts: true,
    proxy: {
      "/api": {
        target: apiTarget,
        changeOrigin: true,
        ws: true,
      },
    },
  },
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    include: ["src/**/*.{test,spec}.{ts,tsx}"],
    css: true,
  },
});
