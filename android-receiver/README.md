# Aether Pagos para Android

Receptor nativo para compartir comprobantes desde WhatsApp directamente al
formulario **Registrar pago** de Aether. Acepta JPEG, PNG, WebP y PDF de hasta
10 MB.

## Flujo

1. Android entrega el archivo a esta aplicación mediante `ACTION_SEND`.
2. La aplicación lo envía autenticado a `/api/v1/payments/shared-receipts`.
3. Aether lo conserva como archivo temporal privado durante un máximo de 24 h.
4. La aplicación abre `/app/?native_receipt=...`; la web recupera el archivo
   una sola vez, lo elimina del área temporal y abre **Registrar pago**.

La contraseña nunca se guarda. El token de sesión se cifra con una clave AES
del Android Keystore y los respaldos de la aplicación están desactivados.

## Compilar

Requiere JDK 17 o posterior, Android SDK 36 y aceptar las licencias del SDK.

```powershell
.\gradlew.bat :app:assembleDebug
```

El APK resultante queda en
`app/build/outputs/apk/debug/app-debug.apk`.
