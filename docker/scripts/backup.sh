#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
DOCKER_DIR=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
ENV_FILE="$DOCKER_DIR/.env.production"
COMPOSE_FILE="$DOCKER_DIR/compose.production.yml"
TIMESTAMP=$(date -u +%Y%m%dT%H%M%SZ)
BACKUP_ROOT=${1:-"$DOCKER_DIR/backups"}
DESTINATION="$BACKUP_ROOT/$TIMESTAMP"

[ -s "$ENV_FILE" ] || {
    printf 'No existe %s\n' "$ENV_FILE" >&2
    exit 1
}

mkdir -p "$DESTINATION"

docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" exec -T postgres \
    sh -c 'exec pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom --no-owner --no-acl' \
    > "$DESTINATION/database.dump"

docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" exec -T backend \
    tar -C /app/backend/private_storage -czf - . \
    > "$DESTINATION/private_storage.tar.gz"

{
    printf 'created_at=%s\n' "$TIMESTAMP"
    printf 'database_format=postgresql_custom\n'
    printf 'private_storage_format=tar_gzip\n'
    if command -v git >/dev/null 2>&1; then
        git -C "$DOCKER_DIR/.." rev-parse HEAD 2>/dev/null | sed 's/^/git_revision=/' || true
    fi
} > "$DESTINATION/manifest.txt"

(
    cd "$DESTINATION"
    sha256sum database.dump private_storage.tar.gz manifest.txt > SHA256SUMS
)

printf 'Respaldo completo: %s\n' "$DESTINATION"
