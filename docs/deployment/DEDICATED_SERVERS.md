# Migración de Aether y UISP a servidores dedicados

## Arquitectura objetivo

- **Servidor Aether:** Caddy, API/PWA de Aether y PostgreSQL mediante Docker
  Compose. PostgreSQL vive en una red interna y no publica el puerto 5432.
- **Servidor UISP:** instalación independiente administrada con el procedimiento
  oficial de UISP. Aether sólo consume su API HTTPS mediante un token de lectura.
- **MikroTik:** permite acceso REST únicamente desde la IP del servidor Aether y
  con cuentas separadas para monitoreo y control.

El servidor Aether expone solamente HTTPS, HTTP para redirección y SSH limitado
a las IP administrativas. Los datos persistentes se encuentran en los volúmenes
`aether_postgres_data` y `aether_private_storage`.

## Paquetes requeridos en el servidor Aether

- Docker Engine y el complemento Docker Compose.
- Git, OpenSSL, `rsync`, `curl` y una cuenta administrativa con acceso a Docker.
- Un nombre DNS para Aether apuntando al servidor y puertos 80/443 accesibles
  para que Caddy obtenga y renueve el certificado TLS.

No es necesario instalar Python, PostgreSQL, LibreOffice ni Node.js en el host;
están encapsulados en las imágenes.

## Preparación del servidor nuevo

1. Clona Aether en una ruta estable, por ejemplo `/opt/aether`.
2. En `docker/`, copia `.env.production.example` como `.env.production` y
   configura el dominio, la URL HTTPS de UISP y las credenciales de MikroTik.
3. Ejecuta `sh docker/scripts/init-secrets.sh` y pega el token de UISP en
   `docker/secrets/uisp_api_token.txt`.
4. Protege los secretos con propietario administrativo y permisos `600`.
5. Ejecuta `sh docker/scripts/preflight.sh`.
6. Inicia con:

   ```sh
   docker compose --env-file docker/.env.production \
     -f docker/compose.production.yml up -d --build
   ```

7. Comprueba `https://DOMINIO/health`, `https://DOMINIO/ready`, el inicio de
   sesión, la consulta de UISP y una simulación —nunca ejecución directa— de
   control MikroTik.

## Respaldo de la instalación actual

Antes del corte debe detenerse temporalmente la captura de datos para obtener un
respaldo coherente. Si la instalación actual ya usa el Compose de producción:

```sh
sh docker/scripts/backup.sh /ruta/segura/aether-backups
```

El resultado contiene:

- `database.dump`, en formato personalizado de PostgreSQL;
- `private_storage.tar.gz`, con contratos, comprobantes y catálogos;
- hashes SHA-256 y un manifiesto.

Los archivos `.env` y los secretos no se incluyen deliberadamente. Deben
trasladarse por un canal cifrado independiente y nunca subirse al repositorio.

Para una instalación anterior, el equivalente mínimo es un `pg_dump` completo y
una copia íntegra de `backend/private_storage`. Ambos elementos pertenecen al
mismo punto temporal.

## Restauración y validación

En un servidor nuevo sin actividad operativa:

```sh
AETHER_CONFIRM_RESTORE=RESTORE \
  sh docker/scripts/restore.sh /ruta/al/respaldo/FECHA
```

La restauración es destructiva sobre los datos que ya existan en el destino.
Después se aplican las migraciones Alembic pendientes y se reinician los
servicios.

Validaciones obligatorias antes del cambio DNS:

1. Cantidades de clientes, servicios, pagos, contratos y activos.
2. Apertura de una muestra de comprobantes y contratos.
3. Inicio de sesión y permisos con cuentas no administrativas.
4. Sincronización de UISP en modo de consulta.
5. Salud de routers y puntos de acceso.
6. Simulación de suspensión/reactivación sin ejecutar el cambio real.
7. Creación de un respaldo nuevo desde el servidor destino.

## Migración separada de UISP

UISP debe migrarse como un proyecto independiente del corte de Aether:

1. Obtén un respaldo verificable de UISP y restaura siguiendo el procedimiento
   de la versión instalada.
2. Conserva, si es posible, el mismo nombre DNS. Esto evita acoplar Aether a una
   dirección IP y facilita volver al servidor anterior.
3. Instala un certificado TLS válido y restringe el firewall de la API a la IP
   del servidor Aether.
4. Emite un token nuevo, exclusivamente de lectura, después de restaurar.
5. Actualiza `UISP_ENDPOINT_URL` y `uisp_api_token.txt`, reinicia Aether y prueba
   la consulta antes de habilitar sincronizaciones programadas.
6. Verifica que los identificadores externos de sitios, clientes y dispositivos
   no hayan cambiado. No ejecutes correcciones masivas si existen diferencias;
   conserva un informe y reconcilia primero una muestra.

Nunca deben operar simultáneamente dos instancias de Aether capaces de escribir
en los mismos MikroTik. Durante el corte, la instancia anterior queda en modo de
consulta o completamente detenida.

## Corte y reversión

1. Reduce el TTL DNS con anticipación.
2. Congela escrituras en Aether anterior.
3. Genera el respaldo final y restáuralo en destino.
4. Ejecuta las validaciones y cambia DNS.
5. Conserva el servidor anterior apagado pero intacto durante el periodo de
   observación.

Para revertir, detén Aether nuevo antes de reactivar el anterior. Si ya hubo
escrituras en el servidor nuevo, no vuelvas simplemente al respaldo viejo:
primero exporta y reconcilia esos cambios para evitar pérdida de operación.

## Operación continua

- Programa `backup.sh` diariamente y copia los respaldos cifrados fuera del
  servidor. Prueba una restauración periódicamente.
- Mantén al menos una copia fuera de línea y aplica una política de retención.
- Actualiza imágenes primero en un entorno de prueba; revisa migraciones y crea
  respaldo antes de cada despliegue.
- Monitorea espacio de PostgreSQL, almacenamiento privado, `/ready`, vencimiento
  TLS y conectividad hacia UISP/MikroTik.
