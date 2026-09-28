# Secretos locales del despliegue

Esta carpeta debe contener tres archivos de una sola línea:

- `postgres_password.txt`: contraseña aleatoria de PostgreSQL.
- `aether_bootstrap_secret.txt`: secreto aleatorio de al menos 32 caracteres.
- `uisp_api_token.txt`: token de solo lectura emitido por UISP.

Los archivos están excluidos de Git. En Linux deben pertenecer al administrador
del servidor y tener permisos `600`. Se pueden crear con `scripts/init-secrets.sh`.
