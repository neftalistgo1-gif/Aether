#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
DOCKER_DIR=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
ENV_FILE="$DOCKER_DIR/.env.production"
COMPOSE_FILE="$DOCKER_DIR/compose.production.yml"

fail() {
    printf 'ERROR: %s\n' "$1" >&2
    exit 1
}

command -v docker >/dev/null 2>&1 || fail "Docker no está instalado."
docker compose version >/dev/null 2>&1 || fail "Falta el complemento Docker Compose."
command -v openssl >/dev/null 2>&1 || fail "OpenSSL no está instalado."

[ -s "$ENV_FILE" ] || fail "Copia .env.production.example como .env.production y complétalo."
for secret in postgres_password aether_bootstrap_secret uisp_api_token; do
    [ -s "$DOCKER_DIR/secrets/$secret.txt" ] || fail "Falta secrets/$secret.txt o está vacío."
done

if grep -Eq '^AETHER_DOMAIN=(aether\.example\.com)?$' "$ENV_FILE"; then
    fail "Configura un dominio real en AETHER_DOMAIN."
fi
if grep -Eq '^UISP_ENDPOINT_URL=https://uisp\.example\.com$' "$ENV_FILE"; then
    fail "Configura la URL real del nuevo servidor UISP."
fi

docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" config --quiet
printf 'Preflight correcto: configuración, secretos y Compose son válidos.\n'
