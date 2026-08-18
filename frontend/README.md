# Interfaz de Aether

La interfaz se mantiene sin dependencias de compilación: los archivos se
cargan en orden desde `index.html` y comparten el objeto `state` definido en
`scripts/app-core.js`.

## Dónde modificar cada cosa

- `scripts/app-core.js`: inicio de sesión, llamadas API, estado compartido y
  resumen principal.
- `scripts/app-assets.js`: inventario y activos físicos.
- `scripts/app-services.js`: clientes, servicios, instalaciones, cortes,
  reactivaciones y bajas.
- `scripts/app-billing.js`: pagos, comprobantes y estados de cuenta.
- `scripts/app-operations.js`: incidencias y soporte.
- `scripts/app-administration.js`: planes, UISP, navegación, sesión y PWA.
- `scripts/app-events.js`: únicamente enlaces de botones, formularios y
  eventos con las funciones de los módulos anteriores.
- `styles.css`: estilos comunes de la aplicación.
- `service-worker.js`: cache de la aplicación instalable. Si se agrega o
  renombra un script, también debe actualizarse aquí y cambiar `CACHE_NAME`.

## Regla de mantenimiento

Una función nueva debe ir en el módulo de su área; el evento de su botón o
formulario va en `app-events.js`. Evita poner reglas de negocio en HTML o
duplicar datos que ya vienen de la API.

Los comentarios explican decisiones no evidentes, límites de seguridad o
compatibilidades externas. No se comenta cada línea: el nombre de funciones y
la división por módulos deben describir el flujo normal.
