#!/bin/sh
set -eu

if [ "$#" -ne 1 ]; then
    printf 'Uso: AETHER_CONFIRM_RESTORE=RESTORE %s /ruta/al/respaldo\n' "$0" >&2
    exit 1
fi
if [ "${AETHER_CONFIRM_RESTORE:-}" != "RESTORE" ]; then
    printf 'La restauración reemplaza la base y archivos actuales. Define AETHER_CONFIRM_RESTORE=RESTORE.\n' >&2
    exit 1
fi

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
DOCKER_DIR=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
ENV_FILE="$DOCKER_DIR/.env.production"
COMPOSE_FILE="$DOCKER_DIR/compose.production.yml"
BACKUP_DIR=$(CDPATH= cd -- "$1" && pwd)

[ -f "$BACKUP_DIR/database.dump" ] || { printf 'Falta database.dump\n' >&2; exit 1; }
[ -f "$BACKUP_DIR/private_storage.tar.gz" ] || { printf 'Falta private_storage.tar.gz\n' >&2; exit 1; }

if [ -f "$BACKUP_DIR/SHA256SUMS" ]; then
    (cd "$BACKUP_DIR" && sha256sum -c SHA256SUMS)
fi

docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" up -d postgres
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" stop backend 2>/dev/null || true

docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" exec -T postgres \
    sh -c 'exec pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists --no-owner --no-acl' \
    < "$BACKUP_DIR/database.dump"

docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" run --rm --no-deps -T backend \
    sh -c 'find /app/backend/private_storage -mindepth 1 -maxdepth 1 -exec rm -rf -- {} + && tar -C /app/backend/private_storage -xzf -' \
    < "$BACKUP_DIR/private_storage.tar.gz"

docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" up -d --build
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" exec -T backend alembic upgrade head

printf 'Restauración terminada. Verifica /ready, el acceso y las integraciones antes del corte DNS.\n'
