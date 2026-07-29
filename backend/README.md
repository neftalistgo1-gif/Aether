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

6. Antes del primer inicio, establecer un valor largo y aleatorio para
   `AETHER_BOOTSTRAP_SECRET` dentro de `.env`.
7. Iniciar la API:

   ```powershell
   python -m uvicorn app.main:app --reload
   ```

La documentación interactiva estará disponible en
`http://127.0.0.1:8000/docs`.

La interfaz operativa estará disponible en `http://127.0.0.1:8000/app/`.
Usa las mismas cuentas y permisos de la API; no requiere iniciar otro proceso
ni instalar herramientas de frontend.

Las cuentas con `customers.write` pueden registrar y editar clientes desde la
interfaz. Toda edición exige un motivo y genera una auditoría con los valores
anteriores y posteriores; las cuentas de consulta no ven estas acciones.

Las cuentas con `services.write`, junto con lectura de clientes y planes,
pueden registrar servicios pendientes. La interfaz sólo usa planes activos con
precio vigente y el backend verifica que `plan_id`, nombre y precio coincidan
con el catálogo. El alta queda auditada y nunca activa automáticamente la
conexión.

Las cuentas con `plans.read` consultan el catálogo completo. Con `plans.write`
pueden crear ofertas, publicar una nueva tarifa y desactivar planes. Cada
cambio exige motivo y conserva el historial; nunca modifica automáticamente
los precios acordados de servicios existentes.

Las cuentas con `installations.write` pueden registrar desde la UI la
evaluación de cobertura de un servicio pendiente. Una evaluación viable se
agenda y genera el cargo correspondiente cuando el costo es mayor que cero;
un resultado fuera de cobertura no se agenda ni cobra. Completar el trabajo y
activar el servicio permanece en un flujo posterior con evidencias obligatorias.
Cuando ya existe una instalación programada, la UI permite reprogramarla o
cancelarla. Ambos caminos exigen motivo; reprogramar conserva el historial y
mueve el vencimiento del cargo, mientras cancelar sólo procede si el cargo no
tiene pagos aplicados.

Completar una instalación inicial desde la UI exige cargo pagado, uno a tres
técnicos, dos a cuatro evidencias de antena, una a cuatro de módem y
confirmación de navegación. Sólo el cierre aprobado activa el servicio. Las
referencias de evidencias permanecen privadas; la API únicamente devuelve sus
conteos.

Las cuentas con `network.control` pueden ejecutar desde la UI una simulación
de suspensión o reactivación para servicios activos o suspendidos. Siempre
envía `dry_run: true`: valida asignación IP y router, genera un comando
idempotente y auditado, pero no modifica MikroTik ni el estado comercial.

Las cuentas con `notifications.write` registran desde cada servicio entregas o
intentos fallidos por WhatsApp, SMS, correo, llamada o aviso presencial. Una
entrega digital exige referencia del proveedor o evidencia privada; un intento
fallido exige un motivo no vacío. Los avisos entregados de suspensión pueden
usarse posteriormente en el flujo comercial coordinado.

## Primer administrador y acceso

Todas las rutas de negocio requieren autenticación. Para preparar una
instalación nueva:

1. Abrir `POST /api/v1/auth/bootstrap` en Swagger.
2. Introducir el valor local de `AETHER_BOOTSTRAP_SECRET` en el encabezado
   `X-Aether-Bootstrap`.
3. Elegir usuario, nombre visible y una contraseña de al menos 12 caracteres.
4. Copiar `access_token` de la respuesta.
5. Pulsar **Authorize** en Swagger e introducir solamente el token.
6. Eliminar `AETHER_BOOTSTRAP_SECRET` de `.env` y reiniciar la API.

El bootstrap deja de funcionar en cuanto existe el primer usuario. En sesiones
posteriores se usa `POST /api/v1/auth/login`. Los tokens vencen después de
`AUTH_SESSION_HOURS` y se almacenan únicamente como SHA-256; las contraseñas
usan `scrypt` con una sal distinta por usuario.

### Permisos operativos

El rol describe el puesto, pero no concede acceso por sí solo. Al crear una
cuenta, el administrador asigna una lista explícita de capacidades mediante
el campo `permissions`. Puede sustituirla posteriormente con
`PUT /api/v1/auth/users/{user_id}/permissions`, indicando el motivo.

Las capacidades separan lectura y escritura por área, además de reservar
decisiones sensibles como `billing.approve`, `incidents.compensate` y
`network.control`. Los procesos diarios usan `operations.read` y
`operations.run`; el historial de comunicación usa `notifications.read` y
`notifications.write`. El administrador tiene acceso total. Los demás usuarios
sólo pueden ejecutar lo que figure expresamente en su cuenta; una ruta nueva
sin política queda denegada hasta que se clasifique.

## Módulos disponibles

- `Authentication`: bootstrap, login, logout, usuarios y permisos operativos.
- `Daily operations`: simulación y ejecución idempotente de mensualidades y
  vencimientos.
- `Notifications`: historial multicanal de entregas e intentos fallidos.
- `Customers`: crear, listar, buscar, consultar y actualizar personas.
- `Services`: crear, listar, buscar, consultar y actualizar conexiones.

Cada Service conserva su precio mensual acordado y se relaciona con su
titular mediante `ServiceHolder`, evitando que el código `AMR###` se use como
identificador permanente de una persona.

### Proceso diario

`POST /api/v1/operations/daily` usa simulación de manera predeterminada. Para
una ejecución real debe enviarse `dry_run: false`; Aether genera únicamente las
mensualidades del mes correspondiente cuya fecha de pago ya llegó y marca las
prórrogas prometidas que vencieron. Una fecha futura se rechaza.

Cada fecha efectiva se ejecuta una sola vez. Repetirla devuelve el resultado
guardado y no duplica cargos. `GET /api/v1/operations/daily` muestra el
historial. Todavía no se conecta un programador externo: primero se valida este
nuevo núcleo y después podrá llamarlo una tarea programada.

Los cambios comerciales y de estado generan eventos auditables. El ciclo de
vida permitido es:

```text
pending -> active -> suspended -> active -> cancelled
```

También se permite cancelar directamente un servicio pendiente, activo o
suspendido. Un servicio cancelado es un estado terminal.

### Operación administrativa

La suspensión exige confirmar que terminó el periodo de tolerancia, que se
revisaron las prórrogas y que no existe una prórroga vigente. También requiere
el `notification_id` de un aviso de suspensión entregado al titular actual y
vinculado al mismo servicio. Conserva la deuda, responsable, notificación y
resultado de MikroTik; un aviso usado por una suspensión exitosa no puede
reutilizarse.

`POST /api/v1/notifications` registra WhatsApp, SMS, correo, llamada o aviso
presencial. Las entregas digitales necesitan referencia del proveedor o
evidencia privada. La API sólo indica si existe evidencia y nunca publica su
ruta interna. Este módulo registra comunicaciones; todavía no envía mensajes
por medio de un proveedor externo.

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

El estado de cuenta consolidado por cliente reúne deuda total, deuda vencida,
cargos abiertos y saldo a favor para una fecha de corte. El cálculo permanece
en la API; la interfaz no reconstruye reglas financieras en el navegador.

### Recepción y verificación de pagos

`Payment` registra el monto declarado, fecha, método, referencia, comprobante,
titular de la cuenta de origen y persona que lo recibió. Todo pago inicia en
`pending`: recibir un comprobante no confirma que el dinero haya ingresado.
La referencia de almacenamiento del comprobante es privada: las respuestas
generales sólo indican `has_proof` y no revelan su ubicación.

Una persona responsable puede verificar el monto realmente recibido, rechazar
el comprobante o cancelar un registro pendiente. Si el monto confirmado es
distinto al declarado, la explicación es obligatoria. Cada transición conserva
responsable, motivo y fecha en `PaymentStatusEvent`.

Los pagos verificados todavía no modifican cargos directamente; su aplicación
a deuda se registra mediante `PaymentAllocation`. Verificar, rechazar, cancelar
y aplicar requieren `billing.approve`; recibir un pago utiliza
`billing.write`.

### Aplicaciones y saldo a favor

Un pago verificado se distribuye por defecto entre los cargos abiertos más
antiguos. También puede dirigirse a cargos específicos si se documenta el
motivo. Cada aplicación reduce el saldo del cargo y lo deja parcial o pagado.

El excedente se registra como un movimiento positivo de saldo a favor. Las
nuevas mensualidades consumen automáticamente ese saldo mediante movimientos
negativos, sin crear mensualidades futuras. Las devoluciones también quedan
registradas y nunca pueden superar el saldo disponible.

### Prórrogas de pago

`Extension` registra la fecha original, nueva fecha prometida, motivo,
autorización y evidencia escrita o digital. Requiere deuda abierta y sólo
puede existir una prórroga activa por servicio.

Una prórroga puede cumplirse, cancelarse o vencer. Antes de suspender, Aether
consulta automáticamente sus registros y bloquea la operación si existe una
prórroga vigente; la deuda no desaparece por concederla.

La suspensión también calcula la deuda directamente desde los cargos abiertos,
exige al menos una mensualidad cuyo periodo de tolerancia haya terminado y
guarda una fotografía de los cargos usados para tomar la decisión. Un monto
manual que no coincida con Aether bloquea el corte.

### Control seguro de MikroTik

Cada router se registra por nombre, URL HTTPS, address list de suspendidos y
una clave de credenciales. Los usuarios y contraseñas nunca se guardan en la
base ni en Git: se leen de variables `MIKROTIK_<CLAVE>_USERNAME` y
`MIKROTIK_<CLAVE>_PASSWORD`.

Las operaciones de suspensión, reactivación y reconciliación usan la IP y el
router de `NetworkAssignment`. El modo de simulación está activo por defecto.
Para operar un router real deben existir sus credenciales y después debe
habilitarse explícitamente su registro.

Cada orden conserva una clave de idempotencia, responsable, IP, intención,
intentos y resultado. Aether consulta la address list después de cada cambio;
sólo marca éxito cuando el estado real coincide. Los fallos pueden reintentarse
y la reconciliación vuelve a aplicar el estado comercial que conserva Aether.

Las rutas coordinadas de suspensión y reactivación validan primero las reglas
comerciales, ejecutan después el cambio de red y sólo actualizan el estado del
servicio cuando MikroTik confirma el resultado. Una simulación o un fallo no
modifica el estado comercial. La orden verificada queda enlazada de forma
única con la suspensión o reactivación que originó.

Las operaciones manuales continúan disponibles para contingencias y quedan
identificadas como `manual`. Ya no es posible declarar un resultado automático
`success` desde las rutas manuales sin una orden MikroTik verificada.

### Incidentes y bonificaciones

`Incident` registra interrupciones o degradaciones por torre, AP o servicio,
con hora exacta de inicio, resolución, causa y responsable. Cada
`IncidentServiceImpact` conserva el servicio y el titular afectado en ese
momento, además de su propio periodo de afectación. Un servicio puede marcarse
como restaurado antes de resolver el incidente general.

Registrar o resolver un incidente no cambia el estado comercial del servicio.
Una vez resuelto, una persona autorizada puede otorgar una sola bonificación
por servicio afectado. La bonificación genera un `CreditMovement` positivo,
queda vinculada al incidente y se incorpora al saldo a favor del titular.

### Auditoría transversal

`AuditEvent` permite consultar acciones críticas por actor, acción y entidad.
Registra el motivo y snapshots mínimos anteriores y posteriores dentro de la
misma transacción del cambio real.

Los eventos confirmados son inmutables: la API sólo permite consultarlos y
PostgreSQL bloquea actualizaciones o eliminaciones. Contraseñas, secretos,
tokens, credenciales y contenido de archivos se excluyen o redactan
automáticamente.

### Catálogo de planes

`Plan` conserva nombre, velocidad, descripción y estado de cada oferta.
`PlanPrice` mantiene todas sus tarifas con fecha inicial y final; cambiar el
precio cierra la vigencia anterior y abre una nueva sin sobrescribir el
historial.

El catálogo y los acuerdos individuales son independientes. Cada `Service`
continúa usando su `monthly_price` acordado, por lo que modificar o desactivar
un plan nunca cambia automáticamente lo que pagan los clientes existentes.

### Cambios de plan por servicio

`ServicePlanChange` registra el plan y precio anteriores, el nuevo acuerdo,
quién lo solicitó, quién aplicó la velocidad y desde qué periodo se cobrará.
El plan operativo cambia el mismo día de la solicitud, pero la nueva tarifa
sólo se usa en la siguiente mensualidad que todavía no haya sido generada.

Cada mensualidad consulta el precio correspondiente a su propio periodo. Una
mensualidad atrasada conserva el precio anterior y un cargo ya creado nunca se
recalcula. Los precios especiales siguen permitidos, pero exigen un motivo
documentado. El endpoint genérico de servicios no acepta cambios de plan,
precio o domicilio; esos campos sólo se modifican mediante sus flujos
especializados.

### Instalaciones y cambios de domicilio

`Installation` administra instalaciones iniciales, reinstalaciones y cambios
de domicilio. Cada registro conserva el resultado de cobertura, fecha
programada, costo, técnicos, evidencias fotográficas y confirmación de
navegación. Las reprogramaciones se almacenan por separado y no sobrescriben
su historial.

Una cobertura no viable no se agenda ni genera cargos. Cuando el trabajo
tiene costo, se crea un cargo real y la instalación no puede completarse hasta
que esté totalmente pagado. La instalación inicial activa el servicio sólo
después de confirmar la navegación; un cambio de domicilio actualiza la
dirección únicamente al completar una nueva cobertura viable.

### Cambio de titular

`HolderTransfer` registra cada transferencia con titular anterior, titular
nuevo, fecha efectiva, responsable, motivo y referencia contractual opcional.
La operación cierra el periodo anterior y abre el nuevo dentro de una sola
transacción; nunca deja dos titulares vigentes.

La transferencia es gratuita y conserva AMR, domicilio, plan, precio, día de
pago, estado y equipo asignado. Tampoco mueve cargos existentes: cada deuda
permanece con la persona responsable cuando se generó. El día efectivo de la
transferencia ya pertenece al nuevo titular, por lo que los cargos creados
desde ese día quedan a su nombre.

### Contratos y anexos

`Contract` conserva folio, titular, servicio, versión, fechas, estado y un
snapshot de domicilio, plan, precio y día de pago. Puede pasar de borrador a
activo, terminar con un folio propio o anularse mientras siga siendo borrador.
Sólo puede existir un contrato activo por servicio y debe terminarse antes de
un cambio de titular.

Los cambios de domicilio y plan agregan `ContractAmendment` al contrato activo
en la misma transacción del cambio real. El archivo firmado sigue fuera del
repositorio: Aether almacena únicamente una referencia privada y, para
evidencia digital, su huella SHA-256. Las respuestas públicas no exponen esa
referencia y todavía no ofrecen carga, descarga o eliminación de documentos.

## Pruebas

Las pruebas usan una base SQLite temporal y no modifican PostgreSQL:

```powershell
python -m unittest discover -s tests -v
```
