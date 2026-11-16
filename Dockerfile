# ARKIS AI LAB — backend Python (y, opcionalmente, la web) en un solo contenedor.
#
# Es el servicio que EJECUTA Python en producción: Netlify no tiene runtime de Python y el
# backend (sesiones en memoria, entrenamientos en segundo plano, persistencia en disco) no
# encaja en funciones serverless. Funciona en cualquier host de contenedores con disco
# persistente (Render, Railway, Fly.io, un VPS...). Ver DOCUMENTACION_DESPLIEGUE_NETLIFY_VERCEL.txt.
#
#   docker build -t arkis-ai-lab .
#   docker run -p 8000:8000 -v arkis-datos:/datos \
#     -e ARKIS_TOKEN=... -e CORS_ORIGINS=https://tu-sitio.netlify.app arkis-ai-lab

# --- Etapa 1: web compilada (rutas relativas: este mismo contenedor también la sirve) ---
FROM node:20-slim AS web
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY index.html vite.config.js ./
COPY src ./src
COPY scripts/build.mjs ./scripts/build.mjs
RUN node scripts/build.mjs --solo=frontend

# --- Etapa 2: backend ---
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_ENV=produccion \
    ARKIS_LAB_DATOS=/datos \
    PORT=8000
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY arkis_lab ./arkis_lab
COPY --from=web /app/dist ./dist
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh \
    && useradd --system --uid 10001 --create-home arkis \
    && mkdir -p /datos && chown arkis:arkis /datos
VOLUME /datos
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
  CMD python -c "import os,urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ[\"PORT\"]}/api/salud', timeout=4)"
# Arranca como root SOLO para ajustar el dueño del disco montado y después ejecuta el
# servidor como 'arkis' (sin privilegios). Un único proceso: el estado vive en memoria y
# en SQLite, así que NO se deben usar varios workers ni varias instancias.
ENTRYPOINT ["docker-entrypoint.sh"]
