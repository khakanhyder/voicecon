FROM node:20-alpine AS base

FROM base AS deps
RUN apk add --no-cache libc6-compat
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci

FROM base AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN mkdir -p public

ARG NEXT_PUBLIC_API_URL=http://backend.15.204.116.11.nip.io
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL

ARG NEXT_PUBLIC_WS_URL=ws://backend.15.204.116.11.nip.io
ENV NEXT_PUBLIC_WS_URL=$NEXT_PUBLIC_WS_URL

ARG NEXT_PUBLIC_GOOGLE_CLIENT_ID=691135919551-nft1jh2neholfputh8sfke93pfmpp5hs.apps.googleusercontent.com
ENV NEXT_PUBLIC_GOOGLE_CLIENT_ID=$NEXT_PUBLIC_GOOGLE_CLIENT_ID

ARG NEXT_PUBLIC_APPLE_CLIENT_ID=
ENV NEXT_PUBLIC_APPLE_CLIENT_ID=$NEXT_PUBLIC_APPLE_CLIENT_ID

ARG NEXT_PUBLIC_APPLE_REDIRECT_URI=http://frontend.15.204.116.11.nip.io/login
ENV NEXT_PUBLIC_APPLE_REDIRECT_URI=$NEXT_PUBLIC_APPLE_REDIRECT_URI

ARG NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY=
ENV NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY=$NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY

ARG NEXT_PUBLIC_APP_NAME=Voicecon
ENV NEXT_PUBLIC_APP_NAME=$NEXT_PUBLIC_APP_NAME

ARG NEXT_PUBLIC_APP_URL=http://frontend.15.204.116.11.nip.io
ENV NEXT_PUBLIC_APP_URL=$NEXT_PUBLIC_APP_URL

ENV NEXT_TELEMETRY_DISABLED=1

RUN npm run build

FROM base AS runner
WORKDIR /app

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

RUN addgroup --system --gid 1001 nodejs
RUN adduser --system --uid 1001 nextjs

RUN mkdir -p .next && chown nextjs:nodejs .next
COPY --from=builder --chown=nextjs:nodejs /app/public ./public

COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs

ENV HOSTNAME="0.0.0.0"

CMD ["node", "server.js"]
