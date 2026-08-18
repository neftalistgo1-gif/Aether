# Guía de desarrollo de Aether

## Propósito

Aether administra la operación de Servicios AMR. Antes de cambiar código,
identifica el módulo de negocio afectado y evita modificar datos operativos o
credenciales como parte de una prueba.

## Mapa del proyecto

- `backend/app/models`: estructura y relaciones de los datos.
- `backend/app/schemas`: contratos de entrada y salida de la API.
- `backend/app/api/v1/endpoints`: reglas de cada módulo y rutas HTTP.
- `backend/app/integrations`: comunicación acotada con UISP y MikroTik.
- `backend/migrations`: cambios versionados de la base de datos.
- `backend/tests`: pruebas de reglas de negocio.
- `frontend`: interfaz; consulta su README antes de modificarla.
- `docs/adr`: decisiones que no deben cambiarse sin una razón explícita.
- `scripts`: automatizaciones locales.

## Procesos delicados

### Sincronización UISP

UISP es la fuente de telemetría; Aether interpreta la información para la
operación. La sincronización es de lectura: nunca debe configurar radios.

`NetworkDevice` conserva el estado actual y `DeviceStatusEvent` únicamente
guarda transiciones. La MAC es la identidad física estable: una readopción de
UISP puede cambiar su identificador interno y debe fusionarse sin duplicar una
antena ni perder historial.

### Suspensión en MikroTik

La lista `desactivados` corta el servicio comercial. No equivale a que una
CPE esté apagada. Aether presenta `Suspendido` por separado de `Sin conexión`.

La excepción de gestión permite solo `TCP 443` hacia el servidor UISP. No se
deben abrir reglas amplias de Internet para recuperar telemetría. Revisa el
orden de reglas antes de modificarlo: una regla de aceptación debe estar antes
del bloqueo aplicable.

### Inventario

Nunca crear un activo físico sin MAC y nombre válidos. Una IP o nombre pueden
cambiar; si la MAC coincide, se actualiza el equipo y se registra el historial
de red. Los datos de clientes no pertenecen a Git.

## Pruebas

Desde la raíz del proyecto, con Docker Desktop activo, ejecuta:

```powershell
.\scripts\test_backend.ps1
```

Las pruebas usan una base SQLite temporal; no consultan UISP, MikroTik ni la
base de datos real. Antes de publicar cambios, ejecuta también una revisión de
formato y comprueba manualmente el flujo afectado en Aether.

## Cambios seguros

1. Lee el ADR y el módulo afectado.
2. Haz el cambio más pequeño que resuelva el problema.
3. Actualiza la prueba y la documentación si cambia una regla de negocio.
4. No subas `backend/.env`, tokens, contraseñas, exportaciones ni datos de
   clientes.
5. Usa commits pequeños con un mensaje que indique la decisión tomada.
