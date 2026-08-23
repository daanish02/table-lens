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
};
module.exports = nextConfig;
