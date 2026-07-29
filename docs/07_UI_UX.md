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
- tablas de servicios y pagos recientes;
- mensajes claros cuando la cuenta no tiene permiso para un área;
- navegación adaptable a escritorio y móvil.

Esta etapa es deliberadamente de consulta. Las acciones que cambian estado se
añadirán módulo por módulo mediante formularios específicos, conservando
confirmaciones, motivos y simulaciones cuando el backend ya las exige.

## Implementación

La superficie actual usa HTML, CSS y JavaScript modular sin dependencias. Se
sirve desde FastAPI para compartir origen con la API, evitar configuración CORS
y no exigir una cadena adicional de compilación. Esta decisión no mueve lógica
de negocio al navegador ni impide migrar a componentes compilados cuando la
complejidad de interacción lo justifique.
