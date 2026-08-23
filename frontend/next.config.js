const path = require("path");
const { loadEnvConfig } = require("@next/env");

// Single .env convention for the whole project — one file at the repo
// root, not a separate frontend/.env.local. @next/env is the same loader
// Next.js itself uses internally for its own .env* files.
loadEnvConfig(path.join(__dirname, ".."));

/** @type {import('next').NextConfig} */
const nextConfig = {
  // Traces only the files a production server actually needs into
  // .next/standalone — the Docker runtime stage copies just that instead of
  // the full node_modules tree. Only set outside Vercel (which sets VERCEL=1
  // during its own builds) — Vercel's serverless pipeline expects its own
  // build output format, not a standalone server.js, and errors with no
  // recognizable output directory if this is left on.
  // Strict equality, not a truthy check — VERCEL set to any other non-empty
  // value (e.g. inherited into a non-Vercel CI shell) would otherwise also
  // disable standalone mode and silently break the Docker build.
  output: process.env.VERCEL === "1" ? undefined : "standalone",
  // Belt-and-suspenders on top of loadEnvConfig() above: Next's dev server
  // compiles pages in a separate worker process that doesn't reliably
  // inherit process.env mutations made here in the main process (confirmed
  // by testing — loadEnvConfig() alone left the client bundle with the
  // hardcoded fallback, not the root .env value). nextConfig.env is read
  // directly by Next at config-build time, not worker-process-dependent,
  // so this is the actually-reliable path for getting a root-.env value
  // into the client bundle's NEXT_PUBLIC_* inlining.
  env: {
    NEXT_PUBLIC_API_BASE_URL: process.env.NEXT_PUBLIC_API_BASE_URL,
  },
};
module.exports = nextConfig;
