# Build a partir da raiz do repositório: docker build -f apps/web/Dockerfile .
FROM node:22-slim AS base
ENV PNPM_HOME=/pnpm PATH=/pnpm:$PATH NEXT_TELEMETRY_DISABLED=1
RUN corepack enable

FROM base AS build
WORKDIR /repo
COPY pnpm-lock.yaml pnpm-workspace.yaml package.json ./
COPY apps/web/package.json apps/web/
COPY packages/api-types/package.json packages/api-types/
RUN pnpm install --frozen-lockfile --filter web...
COPY apps/web apps/web
COPY packages/api-types packages/api-types
RUN pnpm --filter web build

FROM base AS runtime
WORKDIR /app
ENV NODE_ENV=production PORT=3000 HOSTNAME=0.0.0.0
RUN useradd --create-home --uid 1001 web
COPY --from=build --chown=web /repo/apps/web/.next/standalone ./
COPY --from=build --chown=web /repo/apps/web/.next/static ./apps/web/.next/static
USER web
EXPOSE 3000
CMD ["node", "apps/web/server.js"]
