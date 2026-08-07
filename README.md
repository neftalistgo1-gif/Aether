Manifiesto Aether

No construiremos software para administrar clientes.

Construiremos una plataforma que permita comprender el funcionamiento completo de un proveedor de Internet.

Cada pantalla deberá ahorrar tiempo.

Cada botón deberá tener un propósito.

Cada dato deberá existir una sola vez.

Cada proceso repetitivo deberá poder automatizarse.

Toda decisión de diseño deberá facilitar el crecimiento futuro del sistema.

La simplicidad será preferible a la complejidad.

La información será accesible para quien la necesite, protegida para quien no deba verla y registrada para poder auditarla.

Aether crecerá junto con Servicios AMR.

Misión
 
Aether es el espacio donde convergen todos los elementos de un WISP: personas, infraestructura, clientes, pagos, soporte y operación. No reemplaza el trabajo de las personas; las conecta mediante información clara y centralizada.

Vision 


Aether existe para ayudar a pequeños y medianos WISP
a administrar su operación de manera sencilla,
segura y eficiente.

Cada línea de código deberá resolver un problema real.

La simplicidad tendrá prioridad sobre la complejidad.

La documentación tendrá el mismo valor que el código.

Nunca sacrificaremos la estabilidad por agregar funciones.

Construiremos software para personas,
no para impresionar programadores.

## Estado Actual

Aether ya no se piensa como un simple sistema para capturar clientes.
Se está construyendo como una plataforma operativa para un WISP con énfasis en:

- servicios registrables aun cuando el titular esté incompleto al inicio;
- validación posterior de datos faltantes sin romper el flujo operativo;
- cortes y reactivaciones coordinadas con MikroTik;
- comunicación auditable con clientes;
- crecimiento por módulos, no por reescrituras.

La prioridad inmediata es sostener la operación diaria sin obligar a que toda
la ficha del cliente exista desde el primer registro del servicio.

## Puesta en marcha desde GitHub

Cuando quieras instalar Aether en otra PC o servidor:

1. Clona el repositorio desde GitHub.
2. Instala Docker Desktop en la máquina destino.
3. En la raíz del proyecto, copia `backend/.env.example` como `backend/.env`
   y ajusta la cadena de conexión si corresponde.
4. Ejecuta:

   ```powershell
   docker compose -f docker/compose.yml up -d --build
   ```

5. Abre `http://127.0.0.1:8000/app/` o publícalo mediante tu método de acceso
   remoto preferido.

La primera vez también debes definir `AETHER_BOOTSTRAP_SECRET` para crear el
primer administrador y luego retirarlo del `.env`.
## Importacion privada de datos

Si ya preparaste la carpeta local de migracion en `aether_migration/output/`,
puedes cargar clientes, planes y servicios iniciales sin subir nada sensible a
GitHub.

1. Verifica que existan los archivos `customers.csv` y `plans.csv` dentro de
   `aether_migration/output/`.
2. Ejecuta:

   ```powershell
   python backend/scripts/import_migration_data.py
   ```

3. El proceso crea o actualiza clientes, servicios, planes y asignaciones
   actuales a partir de esa carpeta local.
4. Las fechas operativas con dia 29, 30 o 31 se normalizan al dia 1 del mes para
   evitar calendarios invalidos en la importacion.
5. El reporte de importacion se guarda de forma privada en
   `backend/private_storage/import_reports/`.

## Administracion inicial

- El primer administrador se crea desde la pantalla de acceso usando el boton
  de arranque inicial.
- Solo un usuario con rol de administrador puede crear, editar o desactivar
  otros usuarios.
- Los permisos se pueden ajustar por separado sin tocar la contrasena.
- El restablecimiento de contrasena queda como accion independiente para
  conservar trazabilidad.

## Soporte operativo

Aether ya incluye un flujo de tickets para:

- recepcion de comprobantes;
- clasificacion por atencion a clientes;
- derivacion al tecnico cuando el caso sea de red;
- cierre y resolucion con notas de seguimiento.

La idea es que el personal de atencion capture y organice el caso, y que la
parte tecnica actue solo cuando el ticket ya haya sido clasificado.
