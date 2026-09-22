# syntax=docker/dockerfile:1
FROM node:22-bookworm-slim

# Fonts for PDF export, which renders in a headless Chromium with system fonts:
# Noto covers Latin and Khmer (Kantumruy Pro is loaded from Google Fonts when the
# container has internet; these are the offline fallback).
RUN apt-get update \
    && apt-get install -y --no-install-recommends fonts-noto-core fonts-khmeros ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY package.json ./
RUN --mount=type=cache,target=/root/.npm \
    npm install --omit=dev --no-audit --no-fund \
    && npx playwright install --with-deps chromium \
    && rm -rf /var/lib/apt/lists/*

COPY server.mjs paths.mjs ./
RUN mkdir -p work

# No NODE_ENV=production: `slidev export` renders through a Vite dev server, and a
# production-mode Vue never mounts there (the export times out on a hidden <body>).
ENV PORT=3030
EXPOSE 3030
CMD ["node", "server.mjs"]
