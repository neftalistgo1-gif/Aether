$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$backendPath = Join-Path $projectRoot "backend"
$frontendPath = Join-Path $projectRoot "frontend"

# Las pruebas se ejecutan en una base SQLite temporal dentro de un contenedor;
# no usan la base de datos real ni contactan equipos de red.
docker run --rm `
  -v "${backendPath}:/app/backend" `
  -v "${frontendPath}:/app/frontend" `
  -w /app/backend `
  docker-backend:latest `
  python -m unittest discover -s tests -t . -p "test_*.py"
