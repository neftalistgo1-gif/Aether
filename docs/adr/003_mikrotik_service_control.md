# ADR-003: Control de acceso mediante address list de MikroTik

## Estado

Implementado inicialmente

La asignación vigente de router e IP se conserva mediante
`NetworkAssignment`. La ejecución contra equipos reales permanece
deshabilitada por defecto hasta configurar credenciales externas y habilitar
explícitamente cada router.

## Fecha

2026-07-28

## Contexto

Servicios AMR suspende actualmente el acceso a internet agregando la IP del
cliente a una address list de MikroTik. Una regla de red utiliza esa lista
para bloquear el servicio.

Aether deberá poder suspender y reactivar servicios sin convertir a MikroTik
en la fuente de verdad del estado comercial.

## Decisión

La integración futura utilizará la address list existente como mecanismo de
ejecución:

- Suspender: agregar la IP vigente del servicio a la lista de suspendidos.
- Reactivar: retirar la IP vigente del servicio de la lista de suspendidos.
- Verificar: consultar la lista después de cada operación.
- Auditar: conservar solicitud, resultado, respuesta y responsable.

Aether continuará siendo la fuente de verdad. MikroTik reflejará el estado
operativo de acceso a la red.

## Requisitos de implementación

- Relacionar cada Service con su router e IP vigentes.
- Configurar el nombre de la address list por router o entorno.
- Utilizar una cuenta exclusiva con permisos mínimos.
- Conectar mediante HTTPS o API-SSL dentro de una red confiable o VPN.
- Hacer las operaciones idempotentes: agregar una IP ya presente o retirar
  una IP ausente no debe provocar estados inconsistentes.
- Verificar el resultado real antes de marcar la operación como exitosa.
- Permitir reintentos y detectar diferencias entre Aether y MikroTik.
- No almacenar credenciales en Git.

## Consecuencias

### Positivas

- Conserva el mecanismo que Servicios AMR ya conoce.
- Reduce el cambio necesario en la configuración de red.
- Facilita suspensiones y reactivaciones desde Aether.
- Permite reconciliar el estado comercial y el estado real del router.

### Riesgos

- Una IP incorrecta podría afectar a otro cliente.
- Una falla de conexión puede dejar una operación pendiente.
- Los cambios manuales en MikroTik pueden producir diferencias.

Estos riesgos se mitigarán con asignaciones vigentes, verificación posterior,
auditoría y reconciliación periódica.

## Controles implementados

- Registro de routers sin contraseñas en la base de datos ni en Git.
- Credenciales tomadas de variables de entorno por `credential_key`.
- HTTPS obligatorio y validación TLS activada por defecto.
- Modo `dry_run` predeterminado, sin cambios en MikroTik.
- Habilitación explícita por router solamente cuando existen credenciales.
- Claves de idempotencia para impedir ejecuciones duplicadas.
- Verificación de la address list después de agregar o retirar una IP.
- Historial de intentos, resultado, responsable, fechas y errores.
- Reintento del mismo comando sin perder la auditoría anterior.
- Reconciliación tomando el estado comercial de Aether como fuente de verdad.

El control de red no cambia por sí solo el estado comercial del servicio.
Esto evita que una prueba o una falla del router altere suspensiones,
reactivaciones o bajas registradas en Aether.

Las rutas coordinadas agregadas en el módulo 15 realizan la transición
comercial únicamente después de recibir y conservar una verificación exitosa
del router. La suspensión o reactivación resultante referencia la orden de red
que la justificó. Si la IP vigente cambió entre ambas etapas, la transición se
bloquea y exige reconciliación.

El resultado `manual` se conserva para contingencias operativas. El resultado
automático `success` no puede declararse desde las rutas manuales.
