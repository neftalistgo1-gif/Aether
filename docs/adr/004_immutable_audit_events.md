# ADR-004: Eventos de auditoría inmutables

## Estado

Implementado inicialmente

## Fecha

2026-07-28

## Contexto

Aether conserva historiales específicos por módulo, pero las acciones
financieras, comerciales y de red también requieren una vista transversal que
permita responder quién hizo qué, cuándo, sobre qué entidad y por qué.

## Decisión

`AuditEvent` conserva actor, acción, entidad, identificador, fecha, motivo,
datos anteriores y posteriores, además de IP o dispositivo cuando estén
disponibles.

Los eventos se agregan dentro de la misma transacción que la operación de
negocio. Una operación revertida no deja una auditoría falsa. Después de
confirmarse, ningún evento puede modificarse ni eliminarse:

- La API sólo ofrece consultas.
- SQLAlchemy rechaza cambios y eliminaciones.
- PostgreSQL aplica la misma prohibición mediante un trigger.

## Protección de datos

Los snapshots contienen únicamente la información necesaria para explicar la
decisión. No se guardan contraseñas, secretos, tokens, credenciales ni
contenido de archivos. El servicio de auditoría redacta preventivamente
cualquier clave sensible aunque un módulo intente incluirla.

## Cobertura inicial

- Recepción, verificación, rechazo, cancelación y aplicación de pagos.
- Creación, vencimiento, cumplimiento y cancelación de prórrogas.
- Aplicación y devolución de saldo a favor.
- Cancelación de cargos.
- Órdenes de red y sus reintentos.
- Suspensiones, reactivaciones y cancelaciones de servicio.
- Bonificaciones por incidentes.

Los futuros módulos de cambio de titular y documentos personales deberán
registrar sus eventos desde su primera implementación.
