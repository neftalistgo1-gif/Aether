# ADR-009: Notificaciones verificables antes de suspender

## Estado

Implementado

## Fecha

2026-07-28

## Contexto

La regla de suspensión exigía avisar previamente al cliente, pero la solicitud
sólo incluía un indicador y una fecha declarados por el operador. Eso no
demostraba a quién se avisó, por qué canal ni cuál fue el resultado.

## Decisión

Aether conserva un historial de notificaciones con:

- cliente y servicio relacionados;
- canal: WhatsApp, SMS, correo, llamada o presencial;
- finalidad, destinatario y resumen no sensible;
- resultado entregado o fallido;
- referencia del proveedor y referencia privada de evidencia cuando existan;
- fecha real y persona que registró la comunicación.

Las entregas digitales necesitan al menos una referencia externa o evidencia.
La ruta privada de evidencia no aparece en las respuestas de la API.

Una suspensión nueva exige una notificación entregada con finalidad
`suspension_warning`, correspondiente al servicio y al titular actuales. Una
notificación asociada a una suspensión exitosa no puede usarse otra vez. Las
suspensiones históricas conservan sus indicadores anteriores aunque no tengan
el nuevo vínculo.

## Consecuencias

La regla deja de depender de una casilla declarativa y queda lista para que un
proveedor de WhatsApp, SMS o correo registre resultados en el futuro. El envío
automático queda fuera de este módulo para no acoplar el dominio a un proveedor
antes de seleccionarlo.
