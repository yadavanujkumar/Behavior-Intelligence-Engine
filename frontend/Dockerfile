# ---- Build stage ----
FROM node:20-alpine AS build

WORKDIR /app

COPY frontend/package.json ./
RUN npm install --legacy-peer-deps

COPY frontend/ ./
RUN npm run build

# ---- Serve stage ----
FROM nginx:1.25-alpine

COPY --from=build /app/build /usr/share/nginx/html

# nginx config that proxies /api -> api_gateway
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 3000
CMD ["nginx", "-g", "daemon off;"]
