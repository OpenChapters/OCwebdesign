# ---------------------------------------------------------------------------
# OpenChapters — production nginx image (multi-stage)
#
# Builds the React frontend and bundles it into an nginx image that serves
# the SPA and proxies API requests to Django/gunicorn.
#
# Build context: repo root (OCwebdesign/)
# ---------------------------------------------------------------------------

FROM node:20-alpine AS frontend

WORKDIR /build
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install
COPY frontend/ .
RUN npm run build

FROM nginx:alpine

# Remove default nginx site
RUN rm /etc/nginx/conf.d/default.conf

# Copy our config and the built frontend
COPY docker/nginx/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=frontend /build/dist /usr/share/nginx/html

EXPOSE 80
