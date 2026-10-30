# =============================================================================
# Recipe for the FRONTEND container (the website).
#
# Two stages ("multi-stage build"):
#   1. build: use Node.js to turn the React source code into plain HTML/CSS/JS files.
#   2. serve: copy only those finished files into a tiny nginx web server.
# Node and all the build tools are thrown away after stage 1, so the final
# image is small (about 50 MB instead of about 500 MB).
# =============================================================================

# ---- Stage 1: build --------------------------------------------------------
FROM node:22-alpine AS build
WORKDIR /app
# Install dependencies first (cached unless package.json / package-lock.json change).
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
# Copy the source code and build. Output goes to /app/dist.
COPY . .
# Where the website should send API calls. Empty = same address as the website,
# which works because nginx (below) forwards /api to the backend.
ARG VITE_API_URL=""
ENV VITE_API_URL=$VITE_API_URL
RUN npm run build

# ---- Stage 2: serve --------------------------------------------------------
FROM nginx:1.27-alpine
# Our nginx settings (see nginx.conf for what each part does).
COPY nginx.conf /etc/nginx/conf.d/default.conf
# The built website from stage 1.
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 8080
