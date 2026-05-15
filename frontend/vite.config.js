import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 3000,
    /** 占用时直接报错，避免静默改到 3001 等其它端口 */
    strictPort: true,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: false,
        configure: (proxy, _options) => {
          proxy.on("proxyReq", (proxyReq, req) => {
            const m = req.method;
            if ((m === "POST" || m === "PATCH" || m === "PUT") && req.body) {
              proxyReq.setHeader("Content-Length", Buffer.byteLength(req.body));
            }
          });
          proxy.on("proxyRes", (proxyRes, req) => {
            if (req.headers.accept?.includes("text/event-stream")) {
              proxyRes.headers["connection"] = "keep-alive";
            }
          });
        },
      },
    },
  },
});
