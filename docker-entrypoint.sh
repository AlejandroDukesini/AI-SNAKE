#!/bin/sh
# Ajusta el dueño del disco persistente (algunos hosts lo montan como root) y ejecuta el
# servidor sin privilegios. La configuración se valida al importar la app: si falta
# IA_SNAKE_TOKEN en producción, el proceso termina con un mensaje claro.
set -e
mkdir -p "$IA_SNAKE_DATOS"
if [ "$(id -u)" = "0" ]; then
  chown -R iasnake:iasnake "$IA_SNAKE_DATOS"
  exec setpriv --reuid=iasnake --regid=iasnake --init-groups \
    uvicorn ia_snake.servidor.app:app --host 0.0.0.0 --port "$PORT" --workers 1 --proxy-headers
fi
exec uvicorn ia_snake.servidor.app:app --host 0.0.0.0 --port "$PORT" --workers 1 --proxy-headers
