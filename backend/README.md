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

### Operación administrativa

La suspensión exige confirmar que terminó el periodo de tolerancia, que se
revisaron las prórrogas, que no existe una prórroga vigente y que se notificó
al cliente. Conserva la deuda, responsable y resultado de MikroTik.

La reactivación conserva autorización, responsable, deuda y resultado de red.
Los intentos fallidos quedan registrados y pueden reintentarse.

La baja definitiva puede ejecutarse inmediatamente o programarse para una
fecha futura. Conserva titular solicitante, folio, saldos y estado de
recuperación de equipos.

### Recuperación de equipos

La recuperación se programa después de registrar una baja y conserva técnico,
fecha y equipos esperados. Al completar la visita, cada equipo esperado debe
clasificarse como recuperado o faltante.

El resultado se calcula automáticamente:

- `complete`: se recuperaron todos los equipos esperados.
- `partial`: se recuperó una parte y quedaron equipos faltantes.
- `unrecoverable`: no se recuperó ningún equipo.

La finalización también conserva condición, evidencias y constancia de
recepción. Una recuperación no puede completarse antes de ejecutar la baja.

### Inspección y mantenimiento

Cada equipo recuperado inicia en `quarantine` y conserva un historial de
inspecciones con técnico, limpieza, pruebas, reparaciones, evidencias y
dictamen.

Los resultados posibles son:

- `ready_for_reuse`: todas las pruebas fueron aprobadas y se realizó limpieza.
- `needs_repair`: permite reparar y registrar una nueva inspección.
- `defective`: permite diagnosticar o trabajar el equipo y volver a revisarlo.
- `discarded`: el equipo queda fuera de uso de forma definitiva.

Sólo `ready_for_reuse` marca el equipo como reutilizable. Tanto ese resultado
como `discarded` cierran las inspecciones posteriores para evitar cambios
accidentales.

### Inventario y asignaciones

Cada equipo físico se registra como `Asset` con un código interno permanente
`AST-…`. El inventario conserva tipo, descripción, marca, modelo, serie, MAC,
propietario y estado operativo.

Una recuperación genera activos en `quarantine`. Si el equipo ya estaba
registrado, se usa su código `AST-…` para cerrar la asignación anterior sin
crear un duplicado. La inspección actualiza el mismo activo a
`needs_repair`, `defective`, `ready_for_reuse` o `discarded`.

`AssetAssignment` conserva el historial de entregas y devoluciones. Solamente
un servicio activo puede recibir equipos, y únicamente se pueden asignar
activos AMR en estado `available` o `ready_for_reuse`. Un activo no puede
tener dos asignaciones abiertas al mismo tiempo.

### Configuración de red

`NetworkAssignment` conserva la configuración técnica vigente de cada
servicio: IP, router MikroTik, torre, AP, nombre de antena, frecuencia, señal
y técnico responsable.

Cada cambio cierra la configuración anterior y abre una nueva, manteniendo el
historial. Un servicio sólo puede tener una configuración vigente y una misma
combinación de router e IP no puede utilizarse simultáneamente en dos
servicios.

Para evitar inconsistencias con la lista de suspendidos, la configuración no
puede cambiar mientras el servicio esté suspendido. Al ejecutar una baja
definitiva se cierra automáticamente la asignación de red vigente.

### Cargos y saldos

`Charge` representa cada cantidad que debe pagar el titular responsable de un
servicio. Admite instalación, mensualidad, cambio de domicilio, venta de
equipo, servicio adicional, ajuste y otros conceptos.

Las mensualidades se generan mediante una operación especializada que toma el
precio acordado y el día de pago del servicio. No se permiten mensualidades
futuras, anteriores al primer periodo facturable ni duplicadas para el mismo
servicio y periodo.

El saldo conserva deuda total, deuda vencida y número de cargos abiertos. Un
cargo registrado por error se cancela con responsable y motivo; permanece en
el historial y deja de sumar al saldo.

## Pruebas

Las pruebas usan una base SQLite temporal y no modifican PostgreSQL:

```powershell
python -m unittest discover -s tests -v
```
