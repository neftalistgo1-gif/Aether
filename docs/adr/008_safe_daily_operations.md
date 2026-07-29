# ADR-008: Proceso diario simulado, atómico e idempotente

## Estado

Implementado

## Fecha

2026-07-28

## Contexto

Las mensualidades y el vencimiento de prórrogas no deben depender de que una
persona abra cada servicio. Automatizarlos directamente con un programador,
antes de probar la operación central, podría duplicar cargos o dejar cambios
parciales.

## Decisión

Aether incorpora un proceso diario protegido por capacidades:

- la simulación es el valor predeterminado y no modifica datos;
- cada ejecución considera sólo el periodo mensual de la fecha solicitada;
- genera cargos únicamente cuando la fecha de pago ya llegó;
- respeta activación, baja, titular histórico y precio vigente del periodo;
- aplica automáticamente el crédito disponible mediante las reglas existentes;
- vence prórrogas cuya fecha prometida ya pasó;
- rechaza fechas futuras;
- realiza todos los cambios en una sola transacción;
- conserva un resultado único por fecha y repetirlo no duplica operaciones;
- registra un resumen auditable y permite consultar el historial.

## Consecuencias

Una tarea programada podrá invocar este proceso más adelante sin contener
lógica de negocio. Las ejecuciones históricas son explícitas y sólo afectan el
mes seleccionado, evitando facturación retrospectiva accidental.
