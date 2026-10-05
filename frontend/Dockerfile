# syntax=docker/dockerfile:1
FROM node:24-trixie-slim AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

FROM deps AS dev
# source is bind-mounted over /app; node_modules stays in an anonymous volume
COPY . .
EXPOSE 5173
CMD ["npm", "run", "dev"]

FROM deps AS build
COPY . .
RUN npm run build

# Static files served on 5173 so the gateway nginx config is identical in dev and prod.
FROM nginx:1.30-alpine AS prod
COPY docker/nginx-spa.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 5173
