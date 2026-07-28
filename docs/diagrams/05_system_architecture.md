# Arquitectura técnica de Aether

## Propósito

Este diagrama muestra los principales componentes técnicos previstos
para Aether y la forma general en que se comunicarán.

No representa todavía servidores definitivos, puertos, protocolos
detallados ni decisiones de despliegue cerradas.

```mermaid
flowchart TD
    users["Usuarios de Servicios AMR"]

    subgraph clientLayer["Capa de presentación"]
        frontend["Aplicación web<br/>React y TypeScript"]
    end

    subgraph applicationLayer["Capa de aplicación"]
        api["API de Aether<br/>FastAPI"]
        backgroundJobs["Procesos programados<br/>Tareas automáticas"]
    end

    subgraph dataLayer["Capa de datos"]
        database[("PostgreSQL<br/>Datos estructurados")]
        fileStorage[("Almacenamiento privado<br/>Contratos y evidencias")]
    end

    subgraph integrations["Integraciones externas"]
        mikrotik["MikroTik CCR2116"]
        bank["Servicios bancarios"]
        networkDevices["Torres, AP y enlaces"]
    end

    subgraph operations["Operación y seguridad"]
        audit["Auditoría y registros"]
        backups["Respaldos"]
        monitoring["Monitoreo de Aether"]
    end

    users -->|"Usan desde el navegador"| frontend
    frontend -->|"Solicitudes HTTPS"| api

    api -->|"Lee y guarda información"| database
    api -->|"Guarda y consulta archivos"| fileStorage
    api -->|"Registra acciones importantes"| audit

    api -->|"Solicita tareas diferidas"| backgroundJobs
    backgroundJobs -->|"Genera cargos y revisa vencimientos"| database

    api -->|"Operaciones autorizadas"| mikrotik
    api -->|"Conciliación futura"| bank
    api -->|"Consulta técnica futura"| networkDevices

    database -->|"Copias de seguridad"| backups
    fileStorage -->|"Copias de seguridad"| backups

    monitoring -->|"Comprueba disponibilidad"| api
    monitoring -->|"Comprueba ejecución"| backgroundJobs
```