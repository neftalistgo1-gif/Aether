# Modelo conceptual del dominio de Aether

## Propósito

Este documento describe los conceptos principales del negocio de
Servicios AMR y las relaciones entre ellos.

No representa todavía tablas de base de datos ni clases de Python.
Su objetivo es servir como fuente de verdad antes de implementar
el sistema.

---

# 1. Customer

Representa a una persona que ha solicitado, contratado o utilizado
uno o más servicios de Servicios AMR.

## Información principal

- Identificador interno permanente.
- Nombre completo.
- Teléfonos.
- Correo electrónico, cuando exista.
- Identificación oficial.
- Comprobante de domicilio.
- Notas.
- Fecha de registro.

## Reglas

- Un Customer no debe identificarse mediante el código AMR###.
- El historial de una persona no se elimina cuando cancela un servicio.
- Una persona que regresa debe conservar su historial anterior.
- Una deuda pertenece a la persona responsable, no al número AMR.
- Un Customer puede tener más de un Service a lo largo del tiempo.

---

# 2. Service

Representa una conexión de internet contratada y operada en un
domicilio específico.

## Información principal

- Identificador interno permanente.
- Código operativo AMR###.
- Titular actual.
- Dirección actual del servicio.
- Plan contratado.
- Precio mensual acordado.
- Día mensual de pago.
- Días de tolerancia.
- Estado.
- Fecha de activación.
- Fecha efectiva de baja, cuando exista.

## Reglas

- El código AMR### es reutilizable.
- El código AMR### no identifica permanentemente a una persona.
- Un Service puede cambiar de titular.
- Un Service puede cambiar de domicilio.
- Un Service puede cambiar de plan, precio, IP, torre o AP.
- La suspensión no equivale a cancelación.
- Las mensualidades continúan mientras el contrato siga vigente.
- La baja definitiva detiene la generación de nuevas mensualidades.

---

# 3. ServiceHolder

Representa el periodo durante el cual una persona fue titular de
un servicio.

## Información principal

- Customer.
- Service.
- Fecha de inicio.
- Fecha de término.
- Motivo del cambio.
- Contrato relacionado.

## Reglas

- Un Service solamente puede tener un titular vigente a la vez.
- El historial de titulares debe conservarse.
- Cuando cambia el titular, el número AMR y el equipo pueden permanecer.
- Las deudas generadas antes del cambio siguen perteneciendo al titular
  responsable de ese periodo.

---

# 4. Contract

Representa el acuerdo formal entre Servicios AMR y el suscriptor.

## Información principal

- Folio interno.
- Customer.
- Service.
- Fecha de firma.
- Fecha de inicio.
- Versión del contrato.
- Archivo firmado.
- Estado.
- Fecha de terminación.
- Motivo de terminación.

## Reglas

- Los cambios importantes deben conservar evidencia escrita o digital.
- El contrato puede tener vigencia indefinida.
- La terminación debe generar un folio o número de registro.
- Los equipos entregados en comodato deben quedar relacionados con el
  contrato o servicio.
- El contrato original con datos personales no debe almacenarse en un
  repositorio público o de código.

---

# 5. Plan

Representa una oferta comercial de internet.

## Información principal

- Nombre.
- Velocidad.
- Precio vigente.
- Descripción.
- Estado.
- Fecha de inicio de vigencia.
- Fecha de fin de vigencia.

## Reglas

- Cambiar el precio del Plan no modifica automáticamente los servicios
  existentes.
- Cada Service conserva su propio precio mensual acordado.
- Dos clientes con el mismo Plan pueden pagar cantidades diferentes.

---

# 6. Installation

Representa una instalación, reinstalación o cambio de domicilio.

## Información principal

- Service.
- Tipo de trabajo.
- Fecha programada.
- Fecha realizada.
- Técnicos participantes.
- Resultado de cobertura.
- Costo.
- Estado del pago.
- Confirmación de navegación.
- Observaciones.

## Resultados posibles de cobertura

- Viable.
- Requiere equipo especial.
- Fuera de cobertura.

## Evidencias sugeridas

- Fotografías exteriores de la antena.
- Fotografías de los puntos de anclaje.
- Fotografías interiores del módem.
- Fotografías del cableado.
- Confirmación del técnico.
- Confirmación adicional del cliente, cuando exista.

## Reglas

- La visita de cobertura no tiene costo.
- La instalación se paga completamente cuando el servicio ya funciona.
- El servicio debe quedar navegando al finalizar.
- Las reprogramaciones deben conservar motivo e historial.
- Un cambio de domicilio requiere una nueva revisión de cobertura.

---

# 7. Asset

Representa un equipo o material propiedad de Servicios AMR.

## Tipos principales

- Antena.
- Router o módem.
- PoE.
- Fuente de poder.
- Tubo.
- Cable Ethernet.
- Otro.

## Información principal

- Identificador interno.
- Tipo.
- Marca.
- Modelo.
- Número de serie.
- MAC.
- Propietario.
- Estado.
- Fecha de adquisición.
- Notas.

## Estados posibles

- Disponible.
- Asignado.
- En cuarentena.
- Requiere reparación.
- Listo para reutilizarse.
- Defectuoso.
- Desechado.
- No recuperado.
- Vendido al cliente.

## Reglas

- Los equipos en comodato pertenecen a Servicios AMR.
- Los equipos vendidos al cliente no deben recuperarse.
- Una antena, módem, PoE o tubo pueden reasignarse a otro servicio.
- El código AMR### no debe ser el identificador permanente del equipo.
- Cada equipo debe tener un código interno `AST-…` que permanezca durante
  todas sus asignaciones.
- Un equipo recuperado debe permanecer en cuarentena hasta aprobar su
  inspección.

---

# 8. AssetAssignment

Representa la asignación de un equipo a un servicio.

## Información principal

- Asset.
- Service.
- Fecha de entrega.
- Fecha de retiro.
- Condición al entregar.
- Condición al recuperar.
- Propiedad.
- Observaciones.

## Reglas

- Un equipo solamente puede estar asignado a un servicio activo a la vez.
- Debe conservarse todo el historial de asignaciones.
- La recuperación debe registrar quién entregó y quién recibió.
- Los equipos no recuperados deben permanecer como pendientes.
- Sólo los equipos disponibles o listos para reutilizarse pueden asignarse.
- Al recuperar un equipo registrado debe usarse su código `AST-…` para evitar
  crear un activo duplicado.

---

# 9. NetworkAssignment

Representa la configuración técnica actual de un servicio.

## Información principal

- Service.
- IP fija.
- Router MikroTik.
- Torre.
- AP.
- Nombre configurado en la antena.
- Frecuencia y señal observada.
- Fecha de inicio.
- Fecha de término.
- Técnico responsable.

## Reglas

- El nombre visible puede incluir el código AMR### y el nombre del cliente.
- Los cambios frecuentes de AP, frecuencia o IP no deben borrar la
  configuración anterior.
- El historial puede conservarse aunque inicialmente solo se muestre
  la configuración actual.
- Un servicio sólo puede tener una configuración de red vigente.
- La combinación de router e IP debe ser única entre configuraciones vigentes.
- La configuración no puede cambiar mientras el servicio esté suspendido.
- La baja definitiva cierra la configuración vigente.

---

# 10. Charge

Representa una cantidad que una persona debe pagar.

## Tipos principales

- Instalación.
- Mensualidad.
- Cambio de domicilio.
- Equipo vendido.
- Servicio adicional.
- Ajuste.
- Otro.

## Información principal

- Customer responsable.
- Service relacionado.
- Tipo.
- Importe.
- Fecha de generación.
- Fecha de vencimiento.
- Periodo facturado.
- Estado.
- Saldo pendiente.

## Reglas

- Cada mensualidad debe existir como un cargo independiente.
- La mensualidad utiliza el precio acordado vigente del Service al generarse.
- La fecha de vencimiento mensual utiliza el día de pago del Service.
- No deben generarse mensualidades futuras ni duplicadas para un mismo
  periodo.
- La primera mensualidad corresponde al mes posterior a la activación.
- El Customer responsable se determina según la titularidad en la fecha del
  cargo.
- Los cargos no deben eliminarse después de pagarse.
- Un cargo erróneo se cancela conservando responsable, fecha y motivo.
- Los pagos parciales reducen el saldo del cargo.
- Los cargos más antiguos se cubren primero cuando no hay instrucciones.

---

# 11. Payment

Representa dinero declarado o recibido por Servicios AMR.

## Información principal

- Customer.
- Service, cuando aplique.
- Importe.
- Fecha declarada.
- Fecha de recepción.
- Método.
- Referencia.
- Comprobante.
- Titular de la cuenta de origen.
- Estado de verificación.
- Persona que recibió.
- Persona que verificó.

## Estados posibles

- Pendiente de verificación.
- Verificado.
- Rechazado.
- Cancelado.

## Reglas

- Un comprobante no equivale automáticamente a dinero confirmado.
- Todo Payment inicia pendiente de verificación.
- Si el importe confirmado difiere del declarado, debe conservarse una
  explicación.
- Rechazado y cancelado son estados terminales.
- Un Payment verificado puede aplicarse a uno o varios cargos.
- Un pago puede ser parcial.
- Un pago puede generar saldo a favor.
- Todo cambio de estado debe conservar auditoría.

---

# 12. PaymentAllocation

Representa cómo se distribuye un pago entre cargos o saldo a favor.

## Información principal

- Payment.
- Charge.
- Importe aplicado.
- Fecha de aplicación.
- Usuario responsable.

## Reglas

- Un Payment puede tener varias aplicaciones.
- Un Charge puede recibir aplicaciones de varios pagos.
- Primero se cubre la deuda más antigua, salvo instrucción autorizada.
- Una aplicación dirigida exige conservar el motivo.
- Un Payment sólo puede aplicarse una vez y distribuye todo su importe
  confirmado entre deuda y saldo a favor.
- El historial de aplicaciones no debe reemplazarse manualmente.

---

# 13. CreditMovement

Representa los movimientos del saldo a favor.

## Tipos principales

- Pago excedente.
- Aplicación a mensualidad.
- Devolución.
- Ajuste autorizado.

## Información principal

- Customer.
- Service.
- Payment relacionado.
- Charge relacionado.
- Importe.
- Tipo.
- Fecha.
- Usuario responsable.
- Motivo.

## Reglas

- El saldo a favor se calcula mediante movimientos.
- No debe almacenarse únicamente como una cantidad editable.
- El excedente de un pago verificado genera un movimiento positivo.
- Las mensualidades nuevas consumen automáticamente el saldo disponible.
- Una devolución no puede superar el saldo existente.
- Al cancelar, el saldo no utilizado debe resolverse mediante devolución
  o ajuste documentado.

---

# 14. Extension

Representa una prórroga de pago autorizada.

## Información principal

- Customer.
- Service.
- Fecha de pago original.
- Fecha nueva acordada.
- Motivo.
- Persona que autorizó.
- Evidencia escrita o digital.
- Estado.

## Reglas

- Una prórroga vigente puede impedir una suspensión.
- La prórroga no elimina la deuda.
- La autorización y el motivo deben conservarse.
- Los acuerdos verbales deben confirmarse por escrito o digitalmente.

---

# 15. Suspension

Representa una suspensión administrativa por falta de pago.

## Información principal

- Service.
- Fecha programada.
- Fecha ejecutada.
- Motivo.
- Deuda existente.
- Notificación enviada.
- Usuario o proceso responsable.
- Resultado en MikroTik.
- Fecha de reactivación.

## Reglas

- La suspensión no debe ejecutarse solamente porque exista deuda.
- Deben haber transcurrido cinco días naturales posteriores a la fecha
  de pago.
- Debe verificarse que no exista una prórroga vigente.
- Debe registrarse la notificación previa.
- Una interrupción técnica no es una suspensión administrativa.

---

# 16. Cancellation

Representa la solicitud y ejecución de la baja definitiva.

## Información principal

- Service.
- Customer solicitante.
- Fecha de solicitud.
- Fecha efectiva.
- Motivo.
- Folio de cancelación.
- Saldo pendiente.
- Saldo a favor.
- Estado de recuperación de equipos.
- Usuario responsable.

## Reglas

- La solicitud y la fecha efectiva pueden ser diferentes.
- El servicio puede continuar hasta terminar el periodo pagado.
- La baja detiene nuevas mensualidades.
- La deuda anterior no desaparece.
- Debe resolverse el saldo a favor.
- Debe iniciarse la recuperación de equipos.

---

# 17. EquipmentRecovery

Representa el proceso de recuperación de equipos después de una baja.

## Información principal

- Cancellation.
- Fecha programada.
- Técnico asignado.
- Fecha realizada.
- Equipos esperados.
- Equipos recuperados.
- Equipos faltantes.
- Condición.
- Evidencias.
- Constancia de recepción.

## Reglas

- Se prioriza la recuperación de la antena.
- También se intenta recuperar módem, PoE, fuente y tubo.
- Los equipos inaccesibles deben quedar marcados como no recuperados.
- Cada equipo recuperado debe pasar por revisión y mantenimiento.

---

# 18. MaintenanceInspection

Representa la revisión de un equipo recuperado.

## Información principal

- Asset.
- Técnico.
- Fecha.
- Limpieza realizada.
- Pruebas ejecutadas.
- Resultado.
- Reparaciones.
- Estado final.

## Resultados posibles

- Listo para reutilizarse.
- Requiere reparación.
- Defectuoso.
- Desechado.

## Reglas

- Todo equipo recuperado inicia en cuarentena.
- Sólo puede inspeccionarse un equipo registrado como recuperado.
- Para quedar listo para reutilizarse debe haberse limpiado y aprobar todas
  las pruebas registradas.
- Un equipo que requiere reparación o resulta defectuoso puede volver a
  inspeccionarse.
- Listo para reutilizarse y desechado son estados terminales.
- Ningún equipo puede asignarse a otro servicio mientras no esté listo para
  reutilizarse.
- El registro de Aether documenta la decisión operativa y no sustituye una
  certificación técnica o eléctrica cuando ésta sea necesaria.

---

# 19. Incident

Representa una interrupción o degradación técnica del servicio.

## Información principal

- Torre, AP o Service afectado.
- Fecha de inicio.
- Fecha de resolución.
- Causa.
- Servicios afectados.
- Duración.
- Responsable.
- Bonificación aplicable.

## Reglas

- Un Incident no cambia automáticamente el estado comercial del Service.
- Las interrupciones pueden generar compensaciones o bonificaciones.
- Debe conservarse el periodo exacto de afectación.

---

# 20. AuditEvent

Representa una acción importante realizada dentro de Aether.

## Información principal

- Usuario.
- Acción.
- Entidad afectada.
- Identificador.
- Fecha y hora.
- Datos anteriores.
- Datos nuevos.
- Motivo.
- Dirección IP o dispositivo, cuando aplique.

## Acciones que requieren auditoría

- Registro o modificación de pagos.
- Verificación o rechazo de comprobantes.
- Cambios de titular.
- Prórrogas.
- Suspensiones.
- Reactivaciones.
- Cancelaciones.
- Ajustes de saldo.
- Eliminación o acceso a documentos personales.
