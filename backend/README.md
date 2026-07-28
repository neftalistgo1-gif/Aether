# Backend de Aether

API de Aether construida con FastAPI, SQLAlchemy, PostgreSQL y Alembic.

## Preparación local

Desde la carpeta `backend`:

1. Crear y activar un entorno virtual de Python 3.14.
2. Instalar el proyecto:

   ```powershell
   python -m pip install -e .
   ```

3. Copiar `.env.example` como `.env` y ajustar la conexión si es necesario.
4. Iniciar PostgreSQL. Con Docker:

   ```powershell
   docker compose -f ../docker/compose.yml up -d postgres
   ```

5. Aplicar las migraciones:

   ```powershell
   python -m alembic upgrade head
   ```

6. Iniciar la API:

   ```powershell
   python -m uvicorn app.main:app --reload
   ```

La documentación interactiva estará disponible en
`http://127.0.0.1:8000/docs`.

## Módulos disponibles

- `Customers`: crear, listar, buscar, consultar y actualizar personas.
- `Services`: crear, listar, buscar, consultar y actualizar conexiones.

Cada Service conserva su precio mensual acordado y se relaciona con su
titular mediante `ServiceHolder`, evitando que el código `AMR###` se use como
identificador permanente de una persona.

Los cambios comerciales y de estado generan eventos auditables. El ciclo de
vida permitido es:

```text
pending -> active -> suspended -> active -> cancelled
```

También se permite cancelar directamente un servicio pendiente, activo o
suspendido. Un servicio cancelado es un estado terminal.

## Pruebas

Las pruebas usan una base SQLite temporal y no modifican PostgreSQL:

```powershell
python -m unittest discover -s tests -v
```
