#!/bin/sh
set -eu

# Punto de entrada deliberadamente pequeño: prepara permisos y baja privilegios.

storage_dir="${AETHER_PRIVATE_STORAGE_PATH:-/app/backend/private_storage}"

# Los volúmenes montados desde Windows pueden conservar carpetas creadas por
# root. Se corrigen únicamente las rutas que Aether necesita modificar.
mkdir -p "$storage_dir"
chown aether:aether "$storage_dir"

for directory in \
    contracts \
    customer_documents \
    payment_proofs \
    database_backups \
    uisp_batch \
    uisp_monitor
do
    mkdir -p "$storage_dir/$directory"
    chown -R aether:aether "$storage_dir/$directory"
done

if [ -f "$storage_dir/postal_codes.json" ]; then
    chown aether:aether "$storage_dir/postal_codes.json"
fi

# Sólo la preparación del volumen usa root; migraciones y servidor se ejecutan
# con el usuario sin privilegios de Aether.
export HOME=/home/aether
export USER=aether
export LOGNAME=aether
exec setpriv --reuid=10001 --regid=10001 --init-groups "$@"
