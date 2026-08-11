# Telemetria UISP y conectividad de CPE

## Decision

UISP es la fuente de telemetria de red; Aether interpreta esa telemetria en el contexto del negocio. Esta primera etapa es exclusivamente de lectura. No configura radios ni abre conexiones directas a CPE.

`NetworkDevice` conserva el identificador estable de UISP (`uisp_device_id`), su vinculacion opcional con el Service y el AP registrado, el estado actual y las fechas necesarias para la operacion. `DeviceStatusEvent` guarda solamente las transiciones detectadas, no una copia completa de cada muestra de UISP.

## Sincronizacion futura

Un proceso con credenciales de solo lectura consultara UISP y, por cada dispositivo, creara o encontrara el dispositivo por `uisp_device_id`, actualizara datos observados y fechas, y creara un evento solo al cambiar el estado. Al pasar a offline establecera `offline_since`; al recuperar conectividad lo limpiara.

Una AP offline puede explicar varias estaciones offline. Las alertas y el resumen deben senalar esta correlacion antes de recomendar contactar clientes. Offline no prueba que un cliente retiro el equipo.

## API de lectura inicial

- `GET /api/v1/network/devices`: inventario y estado actual.
- `GET /api/v1/services/{service_id}/network-device`: radio vinculado al servicio.
- `GET /api/v1/network/devices/{device_id}/status-events`: historial de transiciones.
- `GET /api/v1/network/daily-summary`: conteos para la vista operativa diaria.
- `GET /api/v1/uisp/connection`: prueba la lectura de UISP sin persistir ni
  exponer su token.

La conexion usa `UISP_ENDPOINT_URL` y `UISP_API_TOKEN` del archivo privado
`backend/.env`. El token debe crearse en UISP con permiso de solo lectura. La
primera llamada consulta `/nms/api/v2.1/devices`; antes de sincronizar se
validara una respuesta real de la instancia AMR para fijar el mapeo de campos.

Los umbrales de alerta no se guardan como reglas fijas en esta fase. El resumen expone los cortes de 24 y 72 horas como referencia operativa; la politica configurable y el envio de avisos se incorporaran despues de validar el flujo diario.

## Comandos futuros

Los cambios de AP, frecuencia, ancho de canal, potencia, firmware o reinicio pertenecen a un modulo separado de comandos UISP. Requeriran autorizacion, validacion, vista previa, confirmacion, auditoria, verificacion posterior y posible reversa. Ninguna ruta de telemetria puede ejecutar esos comandos.
