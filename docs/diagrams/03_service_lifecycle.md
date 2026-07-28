# Ciclo de vida del servicio

## Propósito

Este diagrama representa los estados comerciales de un servicio de
internet y las condiciones que permiten pasar de un estado a otro.

Las interrupciones técnicas de red no aparecen como suspensión,
porque no modifican el estado comercial del servicio.

```mermaid
stateDiagram-v2
    [*] --> CoverageReview: Solicitud recibida

    CoverageReview --> InstallationPending: Cobertura viable
    CoverageReview --> SpecialEquipmentReview: Requiere equipo especial
    CoverageReview --> Rejected: Fuera de cobertura

    SpecialEquipmentReview --> InstallationPending: Solución aprobada
    SpecialEquipmentReview --> Rejected: Instalación no viable

    InstallationPending --> InstallationPending: Reprogramación
    InstallationPending --> Active: Instalación terminada,\npagada y navegando
    InstallationPending --> Cancelled: Cliente desiste

    Active --> Active: Cambio de plan,\nAP, IP o domicilio
    Active --> GracePeriod: Mensualidad no pagada
    Active --> CancellationPending: Cliente solicita baja

    GracePeriod --> Active: Pago verificado
    GracePeriod --> Active: Prórroga autorizada
    GracePeriod --> Suspended: Terminan 5 días naturales,\nsin pago ni prórroga

    Suspended --> Active: Reactivación autorizada
    Suspended --> CancellationPending: Cliente solicita baja
    Suspended --> Cancelled: Terminación conforme al contrato

    CancellationPending --> Active: Solicitud retirada
    CancellationPending --> Cancelled: Finaliza periodo pagado

    Cancelled --> EquipmentRecovery: Generar orden de recuperación
    EquipmentRecovery --> Closed: Recuperación finalizada\no registrada como pendiente

    Rejected --> [*]
    Closed --> [*]
```