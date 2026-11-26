import type { NextConfig } from "next";

const config: NextConfig = {
  output: "standalone",
  poweredByHeader: false,
  serverExternalPackages: ["@node-rs/argon2"],
  // A importação da B3 manda o .xlsx (até 2 MB) por uma server action.
  experimental: { serverActions: { bodySizeLimit: "3mb" } },
  // O navegador precisa ver logo a versão nova do service worker dos alertas.
  async headers() {
    return [{ source: "/sw.js", headers: [{ key: "Cache-Control", value: "no-cache, no-store, must-revalidate" }] }];
  },
};

export default config;
