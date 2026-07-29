# ADR-007: Capacidades explícitas y autorización cerrada

## Estado

Implementado

## Fecha

2026-07-28

## Contexto

Aether conoce los nombres generales de los puestos, pero todavía no existe una
matriz aprobada que defina todas sus responsabilidades reales. Convertir esos
nombres en permisos fijos habría incorporado supuestos operativos difíciles de
cambiar y potencialmente inseguros.

## Decisión

El rol describe el puesto y cada usuario no administrador recibe capacidades
explícitas independientes:

- lectura y escritura se separan por clientes, servicios, facturación,
  contratos, instalaciones, activos, incidentes, red y planes;
- aprobar decisiones financieras, compensar incidentes y controlar la red son
  capacidades específicas;
- ejecutar una baja definitiva requiere `services.cancel`; la edición general
  mediante `services.write` no concede esa decisión terminal;
- consultar auditoría requiere una capacidad propia;
- el administrador conserva acceso total para recuperar y configurar el
  sistema;
- cualquier usuario no administrador carece de acceso hasta que un
  administrador le asigne capacidades;
- cualquier ruta nueva que no tenga una política conocida se deniega de forma
  predeterminada.

Los cambios de capacidades sustituyen el conjunto anterior, exigen un motivo y
generan un evento de auditoría con el estado anterior y posterior.

## Consecuencias

La matriz real puede definirse y ajustarse sin reescribir las reglas de
seguridad ni asociarla rígidamente al nombre de un puesto. La interfaz futura
podrá mostrar u ocultar acciones usando las mismas capacidades, mientras la API
seguirá siendo la autoridad final.
