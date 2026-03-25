FROM node:20.19.0-alpine AS build

WORKDIR /app/apps/web

COPY apps/web/package.json apps/web/package-lock.json ./

RUN npm ci

COPY apps/web /app/apps/web

ARG VITE_API_BASE_URL=/api
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL

RUN npm run build

FROM caddy:2.8-alpine

COPY deploy/staging/Caddyfile /etc/caddy/Caddyfile
COPY --from=build /app/apps/web/dist /srv

EXPOSE 80 443

