Aether v0.0.1-alpha

Logros:
✅ Nombre del proyecto definido.
✅ Visión y misión.
✅ Filosofía del proyecto.
✅ Stack tecnológico elegido.
✅ FastAPI seleccionado.
✅ Arquitectura inicial.
✅ Estructura de carpetas creada.
✅ Inicio de la documentación.

Cambios recientes (2026-07-30):
- Corregido el flujo de acceso al panel al ajustar la carga del frontend y el manejo del login para que la interfaz entre correctamente tras autenticarse.
- Mejorada la inicialización del login para soportar el arranque desde parámetros de URL y evitar bloques en la pantalla de acceso.

Cambios recientes (2026-07-31):
- Mejorado el alta de servicios con búsqueda de cliente titular, captura estructurada del domicilio y autocompletado por código postal desde un catálogo local no versionado.
- Agregado el endpoint protegido `/api/v1/postal-codes` y la documentación para integrar el catálogo postal mediante `AETHER_POSTAL_CODES_PATH` sin subir datos privados al repositorio.
- Añadida la primera vista de operación diaria en la UI para consultar historial, simular ejecuciones y lanzar el proceso real desde una fecha seleccionada.
- Añadido el primer módulo de inventario en la UI con alta de activos, filtros y acciones de asignación o devolución desde el historial del activo.
- Habilitada la carga opcional de imágenes como evidencia privada al cerrar recuperaciones técnicas; la visita puede finalizarse aunque no se adjunten fotos.
- Añadida previsualización de miniaturas para las imágenes de evidencia en el cierre de recuperación antes de confirmar la visita.
