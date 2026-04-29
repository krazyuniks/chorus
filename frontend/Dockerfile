# syntax=docker/dockerfile:1.7

FROM node:22-slim AS base
ARG UID=1000
ARG GID=1000
RUN groupmod -g "$GID" node \
    && usermod -u "$UID" -g "$GID" node \
    && mkdir -p /app \
    && chown node:node /app
WORKDIR /app
USER node

FROM base AS deps
COPY --chown=node:node package.json package-lock.json* ./
RUN if [ -f package-lock.json ]; then npm ci; else npm install; fi

FROM deps AS dev
COPY --chown=node:node . .
EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]

FROM deps AS builder
COPY --chown=node:node . .
RUN npm run build

FROM nginx:1.27-alpine AS runtime
COPY --from=builder /app/dist /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
