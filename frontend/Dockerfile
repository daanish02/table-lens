# Multi-stage build: install deps and run `next build` in a full bun image,
# then copy only the standalone output (a self-contained server + its
# traced node_modules subset, not the full dependency tree) into a lean
# runtime stage.

FROM oven/bun:1-slim AS deps

WORKDIR /app

# Dependency layer first so `docker build` can reuse it whenever only
# application code changes below.
COPY package.json bun.lock ./
RUN bun install --frozen-lockfile

FROM oven/bun:1-slim AS builder

WORKDIR /app

COPY --from=deps /app/node_modules ./node_modules
COPY . .

# NEXT_PUBLIC_* variables are inlined into the client bundle at build time,
# not read at container start — the backend's public URL has to be known
# here. Pass it with: docker build --build-arg NEXT_PUBLIC_API_BASE_URL=...
ARG NEXT_PUBLIC_API_BASE_URL
ENV NEXT_PUBLIC_API_BASE_URL=$NEXT_PUBLIC_API_BASE_URL

RUN bun run build

# Next's standalone output is a plain Node.js server — running it via
# vanilla Node rather than Bun here, since Bun's Node-compat layer has known
# rough edges with Next's standalone server specifically. Bun stays in the
# install/build stages above where it's actually faster.
FROM node:20-slim AS runtime

RUN groupadd --system app && useradd --system --gid app --create-home app

WORKDIR /app

ENV NODE_ENV=production

# `output: "standalone"` (next.config.js) traces only the files this server
# actually needs — no full node_modules tree to copy.
COPY --from=builder --chown=app:app /app/.next/standalone ./
COPY --from=builder --chown=app:app /app/.next/static ./.next/static

USER app

EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD node -e "fetch('http://127.0.0.1:3000/').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"

CMD ["node", "server.js"]
