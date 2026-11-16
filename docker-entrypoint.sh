#!/bin/sh
# Ajusta el dueño del disco persistente (algunos hosts lo montan como root) y ejecuta el
# servidor sin privilegios. La configuración se valida al importar la app: si falta
# ARKIS_TOKEN en producción, el proceso termina con un mensaje claro.
set -e
mkdir -p "$ARKIS_LAB_DATOS"
if [ "$(id -u)" = "0" ]; then
  chown -R arkis:arkis "$ARKIS_LAB_DATOS"
  exec setpriv --reuid=arkis --regid=arkis --init-groups \
    uvicorn arkis_lab.servidor.app:app --host 0.0.0.0 --port "$PORT" --workers 1 --proxy-headers
fi
exec uvicorn arkis_lab.servidor.app:app --host 0.0.0.0 --port "$PORT" --workers 1 --proxy-headers
