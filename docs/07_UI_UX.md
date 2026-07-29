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

## Implementación

La superficie actual usa HTML, CSS y JavaScript modular sin dependencias. Se
sirve desde FastAPI para compartir origen con la API, evitar configuración CORS
y no exigir una cadena adicional de compilación. Esta decisión no mueve lógica
de negocio al navegador ni impide migrar a componentes compilados cuando la
complejidad de interacción lo justifique.
