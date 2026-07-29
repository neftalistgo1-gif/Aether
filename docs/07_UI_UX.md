# UI/UX de Aether

## Principios

- La API es la única autoridad para reglas, permisos y datos.
- La interfaz nunca interpreta una operación denegada como un dato vacío.
- Cada pantalla prioriza el trabajo real antes que adornos o métricas
  inventadas.
- La navegación debe funcionar con teclado, pantallas pequeñas y contraste
  suficiente.
- Los tokens de sesión permanecen en la pestaña actual y se eliminan al cerrar
  sesión; nunca se incluyen credenciales en el código.

## Primera superficie operativa

La primera versión está disponible en `/app/` y utiliza la identidad visual de
Aether. Incluye:

- inicio y cierre de sesión reales;
- nombre, rol y capacidades del operador;
- resumen con clientes, servicios y pagos pendientes de verificación;
- distribución de estados de servicio;
- directorio consultable de clientes;
- alta y edición de clientes para cuentas con `customers.write`;
- tablas de servicios y pagos recientes;
- alta de servicios pendientes mediante selección de titular y plan vigente;
- recepción de pagos pendientes para cuentas con `billing.write`;
- catálogo de planes y tarifas según `plans.read` y `plans.write`;
- mensajes claros cuando la cuenta no tiene permiso para un área;
- navegación adaptable a escritorio y móvil.

Esta etapa es deliberadamente de consulta. Las acciones que cambian estado se
añaden módulo por módulo mediante formularios específicos. El primer flujo de
escritura es la gestión de clientes: compara los valores antes de enviarlos,
evita actualizaciones vacías y exige un motivo que queda en auditoría. Los
flujos siguientes conservarán confirmaciones, motivos y simulaciones cuando el
backend ya las exige.

El alta de servicios sólo aparece cuando la cuenta puede escribir servicios y
consultar al menos un cliente y un plan activo. Nombre y precio se presentan
desde el catálogo; no se capturan como texto libre. La activación permanece en
su flujo especializado y no forma parte del formulario de alta.

La recepción de pagos mantiene separados los pasos financieros. El operador
puede declarar cliente, servicio opcional, monto, medio, fecha y referencias,
pero el registro siempre inicia pendiente. La interfaz advierte que esta acción
no reduce deuda y no ofrece verificar ni aplicar el pago en el mismo formulario.
La ubicación del comprobante se envía como dato privado y nunca regresa en los
listados; éstos sólo indican si existe evidencia.

Las cuentas con `billing.approve` reciben acciones adicionales según el estado.
Un pago pendiente puede verificarse, rechazarse o cancelarse; una diferencia
entre el monto declarado y el confirmado exige explicación. Sólo después de la
verificación aparece la aplicación a deuda. Esta segunda confirmación distribuye
el monto entre cargos abiertos más antiguos y reporta por separado lo aplicado
y el saldo a favor generado.

Las cuentas con `billing.read` pueden abrir el estado de cuenta desde el
directorio de clientes. La vista consulta un resumen calculado por la API y el
historial de cargos; muestra deuda total, deuda vencida, saldo a favor, importes
originales y pendientes. Esta etapa es estrictamente de lectura.

El catálogo comercial muestra planes activos e inactivos. Las cuentas con
`plans.write` pueden crear un plan con su primera tarifa, cambiar el precio
publicado desde una fecha válida o retirar la oferta. La interfaz explica que
ninguna de estas acciones cambia el acuerdo de clientes existentes y conserva
los motivos exigidos por la API.

Para servicios pendientes, `installations.write` habilita la evaluación de
cobertura y la agenda inicial. El formulario distingue cobertura viable,
equipo especial y fuera de cobertura; sólo los resultados viables aceptan
fecha y costo. Registrar esta etapa nunca activa el servicio. Si hay costo, la
API crea el cargo que deberá pagarse antes de completar la instalación.

Si el servicio ya tiene trabajo programado, la misma acción abre su detalle en
lugar de crear otro. Desde allí puede reprogramarse con fecha y motivo, o
cancelarse con motivo. La interfaz deja estas decisiones separadas de la
finalización técnica y refleja que el cargo acompaña la nueva fecha o la
cancelación según las reglas del backend.

El cierre técnico se abre desde una instalación programada. Exige hora real,
técnicos, referencias privadas de las fotografías y la confirmación expresa de
navegación del cliente. La interfaz valida los mínimos de evidencia, pero la
API vuelve a comprobarlos y también bloquea el cierre si el cargo no está
pagado. Sólo una instalación inicial completada por este flujo activa el
servicio.

El control de red comienza en modo seguro. Para `network.control`, los servicios
activos y suspendidos ofrecen una simulación técnica de la acción
correspondiente. El diálogo explica que no es una suspensión comercial, usa una
clave de idempotencia nueva y fuerza `dry_run`. Este control técnico aislado no
ofrece un botón de ejecución real.

**Revisar red** consulta primero la address list sin modificarla y compara el
resultado con el estado comercial. Sólo aparece para servicios activos o
suspendidos con `network.control`. Si ambos estados coinciden, informa que no
hay trabajo pendiente. Si existe una desviación, crea un preflight enlazado a
la inspección y después muestra servicio, IP y efecto esperado; la corrección
real exige código AMR y confirmación. La inspección vence a los cinco minutos,
no puede respaldar dos preflights y pendientes o cancelados no usan esta vía.

La ejecución real sólo se ofrece dentro de suspensión o reactivación comercial
coordinada. Primero se ejecutan todas las validaciones en modo seguro. Si la
simulación es aprobada, una segunda ventana muestra servicio, acción e IP,
explica el efecto operativo, exige escribir el código AMR y confirmar la
revisión. El preflight es de un solo uso, vence en quince minutos y no puede
convertirse mediante reintento.

Cada servicio ofrece registro de comunicaciones a `notifications.write`.
Propósito, canal, resultado, destinatario, hora y resumen se conservan como
datos operativos. Las entregas digitales requieren evidencia o referencia del
proveedor; los intentos fallidos requieren explicación. La ubicación de la
evidencia permanece privada.

La validación comercial de suspensión reúne el saldo calculado por la API y
los avisos entregados del servicio. El operador confirma que revisó tolerancia
y prórrogas, pero el backend vuelve a calcular todas las condiciones. La acción
inicial fuerza `dry_run`; una validación aprobada por sí sola no corta internet
ni cambia el estado del servicio. Sólo habilita la confirmación real separada.

Para servicios suspendidos, la validación coordinada de reactivación consulta
el saldo vigente y muestra deuda total, deuda vencida y cargos abiertos.
Con deuda, reúne las prórrogas y convenios vigentes del titular actual y exige
seleccionar uno; la persona autorizante se completa desde ese registro y no
puede editarse. Con saldo cero permite una autorización directa sin inventar
un acuerdo. La API compara nuevamente deuda, servicio, titular, vigencia y
autorizante. La interfaz fuerza `dry_run`, de modo que una validación correcta
tampoco modifica por sí sola MikroTik ni el estado del servicio. La ejecución
requiere la segunda confirmación y la verificación positiva del router.

La acción de prórrogas abre un historial por servicio y muestra el saldo
actual. Una cuenta con `billing.write` puede registrar fecha original, nueva
fecha prometida, autorización, motivo y evidencia privada cuando existe deuda
y no hay otra prórroga vigente. Resolverla como cumplida o cancelada requiere
`billing.approve`; su historial no se elimina y la referencia interna de
evidencia nunca se presenta en pantalla.

La acción de convenios muestra el saldo, el número de convenios vigentes y el
historial completo. El formulario obliga únicamente a capturar los términos
realmente acordados y quién autorizó; monto, fecha, parcialidades, evidencia y
notas permanecen opcionales. Las cuentas con `billing.approve` seleccionan el
convenio vigente que desean cumplir o cancelar. Ninguna de estas acciones
reduce la deuda ni registra pagos automáticamente.

La baja definitiva se presenta como un expediente de cuatro etapas: solicitud,
corte verificado, recuperación de equipos y liberación de IP. La vista muestra
folio, fecha efectiva, saldos calculados y avance operativo, pero no reproduce
las reglas financieras ni técnicas. `services.cancel` controla solicitud,
ejecución y liberación; `assets.write` permite programar y completar el retiro.

Las dos acciones de MikroTik conservan la secuencia
simulación-confirmación-ejecución y exigen escribir el código AMR antes del
cambio real. La recuperación obliga a clasificar cada equipo esperado como
recuperado o faltante. La liberación sólo aparece después de un resultado final
y exige evidencia privada de desconexión. Si la baja no tenía asignación de
red, la interfaz termina el expediente sin ofrecer una liberación inexistente.

## Implementación

La superficie actual usa HTML, CSS y JavaScript modular sin dependencias. Se
sirve desde FastAPI para compartir origen con la API, evitar configuración CORS
y no exigir una cadena adicional de compilación. Esta decisión no mueve lógica
de negocio al navegador ni impide migrar a componentes compilados cuando la
complejidad de interacción lo justifique.
