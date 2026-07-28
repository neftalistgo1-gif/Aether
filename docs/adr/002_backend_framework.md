# ADR-002: Selección de FastAPI como framework backend

## Estado

Aceptado

## Fecha

2026-07-27

## Contexto

Aether requiere un backend moderno, rápido, tipado y fácil de mantener para administrar la operación de Servicios AMR.

## Decisión

Se utilizará FastAPI como framework principal para el backend.

## Razones

- Excelente rendimiento.
- Documentación automática (OpenAPI / Swagger).
- Tipado mediante Python.
- Integración con Pydantic.
- Arquitectura limpia.
- Gran comunidad.

## Consecuencias

### Positivas

- Desarrollo rápido.
- API autodocumentada.
- Código mantenible.
- Fácil integración con frontend.

### Negativas

- Requiere aprender conceptos ASGI.
- Algunas librerías nuevas pueden tardar en adaptarse a versiones recientes de Python.