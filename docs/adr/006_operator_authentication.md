# ADR-006: Autenticación de operadores con sesiones opacas

## Estado

Implementado inicialmente

## Fecha

2026-07-28

## Contexto

La API contiene pagos, contratos, datos personales y operaciones de red. Los
campos como `performed_by` o `authorized_by` describían el proceso, pero no
demostraban quién había realizado realmente una petición HTTP.

## Decisión

Aether usa usuarios operativos y tokens de sesión opacos:

- las contraseñas se derivan con `scrypt`, sal aleatoria y comparación
  resistente a tiempo;
- el token se entrega una sola vez y PostgreSQL conserva únicamente su
  SHA-256;
- las sesiones tienen vencimiento, pueden revocarse y dejan de funcionar al
  desactivar el usuario o restablecer su contraseña;
- todas las rutas de negocio requieren un usuario activo;
- salud, inicio de sesión y bootstrap inicial son las únicas excepciones;
- la creación y administración de usuarios exige rol `administrator`;
- la auditoría vincula el evento al usuario autenticado y sustituye cualquier
  nombre de actor declarado por el cuerpo de la petición.

El primer administrador se crea mediante un bootstrap de un solo uso protegido
por `AETHER_BOOTSTRAP_SECRET`. Después de crear el primer usuario, la operación
queda bloqueada por el estado de la base de datos. El secreto debe eliminarse
del entorno y la API debe reiniciarse.

## Alcance pendiente

Los roles se registran desde ahora, pero este módulo sólo aplica autenticación
global y administración exclusiva para administradores. La autorización fina
por operación se implementará en un módulo posterior, después de documentar la
matriz exacta de responsabilidades.
