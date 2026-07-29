# ADR-005: Evidencia contractual privada por referencia

## Estado

Implementado inicialmente

## Fecha

2026-07-28

## Contexto

Los contratos firmados contienen datos personales y no deben guardarse en el
repositorio, en eventos de auditoría ni exponerse mediante consultas generales
de la API. Aether todavía no cuenta con autenticación, autorización por roles
ni un almacén privado de documentos listo para producción.

## Decisión

El módulo contractual guarda en PostgreSQL el folio, estado, titular, servicio,
versión, fechas, snapshots del acuerdo y una referencia opaca a la evidencia.
Para documentos digitales también exige una huella SHA-256 que permita
comprobar su integridad.

El contenido del archivo no se almacena en PostgreSQL ni en Git. Las respuestas
`ContractRead` indican si existe evidencia y muestran su huella, pero excluyen
la referencia física o digital. Tampoco existen todavía endpoints de descarga
o eliminación.

Las rutas `private_storage/` están excluidas del repositorio preventivamente.
Cuando se implemente el almacenamiento definitivo, deberá incluir:

- autenticación y autorización por rol;
- cifrado en reposo y durante la transferencia;
- nombres internos aleatorios sin datos personales;
- registro auditable de accesos y eliminaciones;
- copias de seguridad y política de retención;
- validación de tipo, tamaño y contenido del archivo.

## Consecuencias

El registro contractual y sus reglas pueden usarse desde ahora sin fingir que
el archivo ya está protegido. La carga y descarga se habilitarán únicamente
cuando la capa de seguridad correspondiente esté lista.
