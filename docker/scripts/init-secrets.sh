#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
SECRETS_DIR="$SCRIPT_DIR/../secrets"

umask 077
mkdir -p "$SECRETS_DIR"

create_random_secret() {
    target=$1
    if [ ! -s "$target" ]; then
        openssl rand -hex 32 > "$target"
        printf 'Creado %s\n' "$target"
    fi
}

create_random_secret "$SECRETS_DIR/postgres_password.txt"
create_random_secret "$SECRETS_DIR/aether_bootstrap_secret.txt"

if [ ! -e "$SECRETS_DIR/uisp_api_token.txt" ]; then
    : > "$SECRETS_DIR/uisp_api_token.txt"
    printf 'Creado %s; pega aquí el token de solo lectura de UISP.\n' \
        "$SECRETS_DIR/uisp_api_token.txt"
fi

chmod 600 "$SECRETS_DIR"/*.txt
