FROM node:20-alpine AS base
RUN corepack enable

# Stage 1: Extract and install dependencies
FROM base AS deps
WORKDIR /app

# Copy the monorepo workspace configurations
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY apps/web/package.json ./apps/web/
COPY packages/shared-types/package.json ./packages/shared-types/

RUN pnpm install --frozen-lockfile

# Stage 2: Build the Next.js application
FROM base AS builder
WORKDIR /app

# Copy all source files and the installed dependencies
COPY . .
COPY --from=deps /app/node_modules ./node_modules
COPY --from=deps /app/apps/web/node_modules ./apps/web/node_modules
COPY --from=deps /app/packages/shared-types/node_modules ./packages/shared-types/node_modules

WORKDIR /app/apps/web

# Note: Because env.ts is configured to fail-fast on missing variables, 
# build-time environment variables (like NEXT_PUBLIC_ map tokens) must be present. 
# Railway will inject these automatically during deployment.
RUN pnpm run build

# Stage 3: Production runner
FROM base AS runner
WORKDIR /app

ENV NODE_ENV=production
ENV PORT=3000

RUN addgroup --system --gid 1001 nodejs && \
    adduser --system --uid 1001 nextjs

# Copy the Next.js standalone build output
# In a monorepo, the standalone folder mirrors the workspace structure
COPY --from=builder /app/apps/web/public ./apps/web/public
COPY --from=builder --chown=nextjs:nodejs /app/apps/web/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/apps/web/.next/static ./apps/web/.next/static

USER nextjs
EXPOSE 3000

# Execute the standalone Next.js server from the monorepo root path
CMD ["node", "apps/web/server.js"]