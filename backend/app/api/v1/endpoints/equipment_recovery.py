from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.v1.endpoints.services import find_service_or_404
from app.db.session import get_db
from app.models.equipment_recovery import EquipmentRecovery
from app.models.service_operations import (
    Cancellation,
    CancellationStatus,
    EquipmentRecoveryStatus,
)
from app.schemas.equipment_recovery import (
    EquipmentRecoveryComplete,
    EquipmentRecoveryCreate,
    EquipmentRecoveryRead,
)

router = APIRouter(prefix="/api/v1/services", tags=["equipment recovery"])

FINAL_RECOVERY_STATUSES = {
    EquipmentRecoveryStatus.partial,
    EquipmentRecoveryStatus.complete,
    EquipmentRecoveryStatus.unrecoverable,
}


def find_cancellation_or_404(
    service_id: UUID,
    db: Session,
) -> Cancellation:
    cancellation = db.scalar(
        select(Cancellation).where(Cancellation.service_id == service_id)
    )
    if cancellation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cancellation not found",
        )
    return cancellation


def find_recovery_or_404(
    cancellation_id: UUID,
    db: Session,
) -> EquipmentRecovery:
    recovery = db.scalar(
        select(EquipmentRecovery).where(
            EquipmentRecovery.cancellation_id == cancellation_id
        )
    )
    if recovery is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Equipment recovery not found",
        )
    return recovery


@router.post(
    "/{service_id}/equipment-recovery",
    response_model=EquipmentRecoveryRead,
    status_code=status.HTTP_201_CREATED,
)
def create_equipment_recovery(
    service_id: UUID,
    recovery_data: EquipmentRecoveryCreate,
    db: Session = Depends(get_db),
) -> EquipmentRecovery:
    find_service_or_404(service_id, db)
    cancellation = find_cancellation_or_404(service_id, db)
    if recovery_data.scheduled_for < cancellation.effective_date:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Equipment recovery cannot be scheduled before "
                "the effective cancellation date"
            ),
        )

    recovery = EquipmentRecovery(
        cancellation_id=cancellation.id,
        status=EquipmentRecoveryStatus.scheduled,
        **recovery_data.model_dump(),
    )
    cancellation.equipment_recovery_status = (
        EquipmentRecoveryStatus.scheduled
    )
    db.add(recovery)

    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Equipment recovery already exists for this cancellation",
        ) from error

    db.refresh(recovery)
    return recovery


@router.get(
    "/{service_id}/equipment-recovery",
    response_model=EquipmentRecoveryRead,
)
def get_equipment_recovery(
    service_id: UUID,
    db: Session = Depends(get_db),
) -> EquipmentRecovery:
    find_service_or_404(service_id, db)
    cancellation = find_cancellation_or_404(service_id, db)
    return find_recovery_or_404(cancellation.id, db)


@router.post(
    "/{service_id}/equipment-recovery/complete",
    response_model=EquipmentRecoveryRead,
)
def complete_equipment_recovery(
    service_id: UUID,
    completion: EquipmentRecoveryComplete,
    db: Session = Depends(get_db),
) -> EquipmentRecovery:
    find_service_or_404(service_id, db)
    cancellation = find_cancellation_or_404(service_id, db)
    if cancellation.status != CancellationStatus.executed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cancellation must be executed before equipment recovery",
        )

    recovery = find_recovery_or_404(cancellation.id, db)
    if recovery.status in FINAL_RECOVERY_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Equipment recovery is already complete",
        )

    expected = {item.casefold() for item in recovery.expected_equipment}
    recovered = {
        item.casefold() for item in completion.recovered_equipment
    }
    missing = {item.casefold() for item in completion.missing_equipment}
    unclassified = expected - recovered - missing
    if unclassified:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": "Every expected equipment item must be classified",
                "unclassified": sorted(unclassified),
            },
        )

    if not recovered:
        recovery_status = EquipmentRecoveryStatus.unrecoverable
    elif missing:
        recovery_status = EquipmentRecoveryStatus.partial
    else:
        recovery_status = EquipmentRecoveryStatus.complete

    recovery.status = recovery_status
    recovery.performed_at = datetime.now(UTC)
    recovery.performed_by = completion.performed_by
    recovery.recovered_equipment = completion.recovered_equipment
    recovery.missing_equipment = completion.missing_equipment
    recovery.condition_notes = completion.condition_notes
    recovery.evidence_references = completion.evidence_references
    recovery.receipt_reference = completion.receipt_reference
    recovery.notes = completion.notes
    cancellation.equipment_recovery_status = recovery_status

    db.commit()
    db.refresh(recovery)
    return recovery
