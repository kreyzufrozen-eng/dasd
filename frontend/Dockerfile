# syntax=docker/dockerfile:1

# ---- deps: install dependencies only (cached separately from source) ----
FROM node:20-alpine AS deps
WORKDIR /app
COPY package.json ./
RUN npm install

# ---- build: compile the Next.js app ----
FROM node:20-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .

# See the long comment in next.config.js: NEXT_PUBLIC_* vars are inlined at
# build time. docker-compose.yml only sets NEXT_PUBLIC_API_URL as a runtime
# `environment:` value (no build args configured), so this ARG/ENV pair
# defaults to the same URL used elsewhere in the repo's .env.example. Pass
# `--build-arg NEXT_PUBLIC_API_URL=...` (e.g. via
# `docker compose build --build-arg NEXT_PUBLIC_API_URL=...`) at build time
# if the deployed backend lives at a different URL than the default.
ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}
# Same build-time inlining as NEXT_PUBLIC_API_URL — see docker-compose.yml
# for the trade-offs of shipping this in the client bundle.
ARG NEXT_PUBLIC_API_KEY=""
ENV NEXT_PUBLIC_API_KEY=${NEXT_PUBLIC_API_KEY}
ARG NEXT_PUBLIC_SUPPORT_EMAIL="support@readhunter.example"
ENV NEXT_PUBLIC_SUPPORT_EMAIL=${NEXT_PUBLIC_SUPPORT_EMAIL}
ENV NEXT_TELEMETRY_DISABLED=1

RUN npm run build

# ---- runner: minimal production image ----
FROM node:20-alpine AS runner
WORKDIR /app

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
# Also set at runtime so `docker compose`'s `environment: NEXT_PUBLIC_API_URL`
# is visible to server-side code (e.g. any server components/route handlers
# reading process.env directly). Client-bundle values were already baked in
# at build time above and are NOT affected by this.
ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}
ENV PORT=3000
ENV HOSTNAME=0.0.0.0

RUN addgroup --system --gid 1001 nodejs \
  && adduser --system --uid 1001 nextjs

# standalone output: minimal server.js + only-needed node_modules
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public

USER nextjs

EXPOSE 3000

CMD ["node", "server.js"]
