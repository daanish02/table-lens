/** @type {import('next').NextConfig} */
const nextConfig = {
  // Traces only the files a production server actually needs into
  // .next/standalone — the Docker runtime stage copies just that instead of
  // the full node_modules tree. Only set outside Vercel (which sets VERCEL=1
  // during its own builds) — Vercel's serverless pipeline expects its own
  // build output format, not a standalone server.js, and errors with no
  // recognizable output directory if this is left on.
  output: process.env.VERCEL ? undefined : "standalone",
};
module.exports = nextConfig;
