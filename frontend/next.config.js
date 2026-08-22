/** @type {import('next').NextConfig} */
const nextConfig = {
  // Traces only the files a production server actually needs into
  // .next/standalone — the Docker runtime stage copies just that instead of
  // the full node_modules tree.
  output: "standalone",
};
module.exports = nextConfig;
