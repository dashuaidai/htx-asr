# Task 5 — Search-UI frontend container.
# Multi-stage: build the React app with node, serve it with nginx on :3000.

# ---- build stage ----
FROM node:18-alpine AS build
WORKDIR /app
COPY package.json ./
RUN npm install --legacy-peer-deps
COPY public ./public
COPY src ./src
RUN npm run build

# ---- runtime stage ----
FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/build /usr/share/nginx/html
EXPOSE 3000
