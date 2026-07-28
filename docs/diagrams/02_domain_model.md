# Modelo de dominio de Aether

## Propósito

Este diagrama representa los conceptos principales de Servicios AMR
y las relaciones existentes entre ellos.

No representa todavía tablas de PostgreSQL ni clases de Python.

```mermaid
flowchart TD
    customer["Customer<br/>Persona o suscriptor"]
    serviceHolder["ServiceHolder<br/>Periodo de titularidad"]
    service["Service<br/>Servicio de internet"]
    contract["Contract<br/>Contrato"]
    plan["Plan<br/>Plan comercial"]

    installation["Installation<br/>Instalación o traslado"]
    networkAssignment["NetworkAssignment<br/>IP, torre y AP"]

    assetAssignment["AssetAssignment<br/>Asignación de equipo"]
    asset["Asset<br/>Equipo o material"]

    charge["Charge<br/>Cargo"]
    payment["Payment<br/>Pago recibido"]
    paymentAllocation["PaymentAllocation<br/>Aplicación del pago"]
    creditMovement["CreditMovement<br/>Saldo a favor"]

    extension["Extension<br/>Prórroga"]
    suspension["Suspension<br/>Suspensión administrativa"]
    cancellation["Cancellation<br/>Baja definitiva"]
    equipmentRecovery["EquipmentRecovery<br/>Recuperación de equipos"]

    customer -->|"puede ser titular mediante"| serviceHolder
    serviceHolder -->|"pertenece a"| service

    customer -->|"firma"| contract
    contract -->|"formaliza"| service

    service -->|"contrata"| plan
    service -->|"requiere"| installation
    service -->|"tiene configuración"| networkAssignment

    service -->|"recibe equipos mediante"| assetAssignment
    assetAssignment -->|"asigna"| asset

    customer -->|"es responsable de"| charge
    service -->|"genera"| charge

    customer -->|"realiza"| payment
    payment -->|"se distribuye mediante"| paymentAllocation
    paymentAllocation -->|"cubre"| charge
    payment -->|"puede generar"| creditMovement
    creditMovement -->|"puede aplicarse a"| charge

    service -->|"puede recibir"| extension
    service -->|"puede sufrir"| suspension
    service -->|"puede terminar mediante"| cancellation
    cancellation -->|"inicia"| equipmentRecovery
    equipmentRecovery -->|"recupera"| assetAssignment
```