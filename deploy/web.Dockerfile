# The public web image (RM-281): the SPA, built once here, served by Caddy together with the reverse proxy to the
# API. Node exists only in the build stage; the runtime image is Caddy and static files (agents.md §2: Python is
# the only server runtime). HTML and its hashed assets come from one build, so a release is always coherent.
# Build context: the repository root (deploy/web.Dockerfile.dockerignore keeps it to frontend/ and deploy/).

FROM node:24.22.0-bookworm-slim AS build
WORKDIR /app
RUN corepack enable
COPY frontend/package.json frontend/pnpm-lock.yaml frontend/.node-version ./
RUN pnpm install --frozen-lockfile
COPY frontend/ ./
# A public value (a Google OAuth client id is not a secret); empty means "no Google button" (GoogleButton says so).
ARG VITE_GOOGLE_CLIENT_ID=""
ENV VITE_GOOGLE_CLIENT_ID=${VITE_GOOGLE_CLIENT_ID}
# The production build, then the same gate CI runs: no test tooling in dist/, bundle within budget.
RUN pnpm build && node check-dist.mjs

FROM caddy:2.11.4-alpine
COPY --from=build /app/dist /srv/spa
COPY deploy/Caddyfile /etc/caddy/Caddyfile
