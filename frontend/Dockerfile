# Build context: repository root (needs deploy/nginx/nginx.conf)
# docker build -f frontend/Dockerfile .

# ---- 1. build the React app ----
FROM node:20-alpine AS build
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# ---- 2. serve static files with Nginx (runs as non-root, port 8080) ----
FROM nginxinc/nginx-unprivileged:1.27-alpine
COPY deploy/nginx/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s CMD wget -qO- http://127.0.0.1:8080/ >/dev/null || exit 1
