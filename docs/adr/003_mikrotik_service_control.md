# ADR-003: Control de acceso mediante address list de MikroTik

## Estado

Aceptado

La asignación vigente de router e IP ya se conserva mediante
`NetworkAssignment`. La conexión automática con MikroTik continúa pendiente.

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
