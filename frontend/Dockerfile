FROM node:20-alpine AS base

WORKDIR /app
RUN apk add --no-cache libc6-compat
RUN npm install -g pnpm

FROM base AS deps
COPY package.json pnpm-lock.yaml* ./
RUN pnpm install --frozen-lockfile

FROM base AS builder
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN pnpm build

FROM base AS runner
ENV NODE_ENV=production
COPY --from=builder /app ./
EXPOSE 5000
CMD ["pnpm", "start"]
