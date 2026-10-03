# Etapa 1: compila la aplicación con Node.
FROM node:24-alpine AS build
WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci --no-fund --no-audit

COPY . .
# Ruta relativa: nginx reenvía /graphql al gateway, así el navegador habla con
# un solo origen y la cookie de sesión viaja sin depender de CORS.
ARG VITE_GRAPHQL_URL=/graphql
ENV VITE_GRAPHQL_URL=$VITE_GRAPHQL_URL
RUN npm run build

# Etapa 2: sirve los archivos estáticos con nginx.
FROM nginx:1.29-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
HEALTHCHECK --interval=10s --timeout=3s --retries=5 CMD wget -qO /dev/null http://127.0.0.1/ || exit 1
