# Build the SPA, then serve the static bundle from nginx (ADR-017). nginx also
# reverse-proxies /api to the api service, so the browser only calls same-origin.
FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
