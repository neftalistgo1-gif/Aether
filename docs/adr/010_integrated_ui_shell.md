# ADR-010: Primera interfaz integrada y sin dependencias

## Estado

Implementado

## Fecha

2026-07-28

## Contexto

El núcleo ya dispone de autenticación, autorización por capacidades y contratos
estables para las consultas principales. La estación de desarrollo no tiene
Node.js instalado y añadir una segunda cadena de ejecución sólo para mostrar
las primeras pantallas aumentaría el riesgo sin mejorar las reglas de negocio.

## Decisión

La primera UI:

- vive aislada dentro de `frontend`;
- se sirve en `/app/` desde la misma aplicación FastAPI;
- usa HTML, CSS y JavaScript sin dependencias externas;
- inicia y cierra sesión contra la API real;
- conserva el token sólo en `sessionStorage`;
- consulta clientes, servicios y pagos según las capacidades del usuario;
- representa permisos denegados de forma explícita;
- comienza como superficie de consulta responsiva.

La API continúa siendo la única autoridad. La interfaz no replica validaciones
comerciales ni contiene credenciales.

## Consecuencias

La UI puede usarse sin instalar ni ejecutar otro entorno, y su carpeta sigue
separada del backend. Si las interacciones futuras justifican una herramienta
de componentes y compilación, podrá incorporarse dentro de la misma superficie
sin cambiar los endpoints ni las reglas existentes.
