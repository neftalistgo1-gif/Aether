from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.v1.endpoints.services import find_service_or_404
from app.db.session import get_db
from app.models.asset import (
    Asset,
    AssetAssignment,
    AssetOwner,
    AssetReturnOutcome,
    AssetStatus,
    AssetType,
)
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


def infer_asset_type(equipment_name: str) -> AssetType:
    normalized = equipment_name.casefold()
    if "antena" in normalized:
        return AssetType.antenna
    if "modem" in normalized or "módem" in normalized or "router" in normalized:
        return AssetType.router_modem
    if normalized == "poe" or "poe" in normalized:
        return AssetType.poe
    if "fuente" in normalized:
        return AssetType.power_supply
    if "tubo" in normalized or "mástil" in normalized or "mastil" in normalized:
        return AssetType.mast
    if "ethernet" in normalized or "cable" in normalized:
        return AssetType.ethernet_cable
    return AssetType.other


def find_asset_by_internal_code(
    equipment_name: str,
    db: Session,
) -> Asset | None:
    return db.scalar(
        select(Asset).where(
            func.lower(Asset.internal_code) == equipment_name.casefold()
        )
    )


def close_active_assignment(
    asset: Asset,
    service_id: UUID,
    performed_by: str,
    condition_notes: str,
    outcome: AssetReturnOutcome,
    db: Session,
) -> AssetAssignment:
    assignment = db.scalar(
        select(AssetAssignment).where(
            AssetAssignment.asset_id == asset.id,
            AssetAssignment.service_id == service_id,
            AssetAssignment.returned_at.is_(None),
        )
    )
    if assignment is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Asset {asset.internal_code} is not actively assigned "
                "to this service"
            ),
        )
    assignment.returned_at = datetime.now(UTC)
    assignment.returned_by = performed_by
    assignment.condition_on_return = condition_notes
    assignment.return_outcome = outcome
    return assignment


def synchronize_recovery_inventory(
    service_id: UUID,
    recovery: EquipmentRecovery,
    completion: EquipmentRecoveryComplete,
    db: Session,
) -> None:
    for equipment_name in completion.recovered_equipment:
        asset = find_asset_by_internal_code(equipment_name, db)
        if asset is None:
            asset = Asset(
                internal_code=f"AST-{uuid4().hex[:12].upper()}",
                asset_type=infer_asset_type(equipment_name),
                description=equipment_name,
                owner=AssetOwner.amr,
            )
            db.add(asset)
        else:
            close_active_assignment(
                asset,
                service_id,
                completion.performed_by,
                completion.condition_notes,
                AssetReturnOutcome.recovered,
                db,
            )
        asset.latest_recovery_id = recovery.id
        asset.recovery_equipment_name = equipment_name
        asset.status = AssetStatus.quarantine

    for equipment_name in completion.missing_equipment:
        asset = find_asset_by_internal_code(equipment_name, db)
        if asset is None:
            continue
        close_active_assignment(
            asset,
            service_id,
            completion.performed_by,
            completion.condition_notes,
            AssetReturnOutcome.not_recovered,
            db,
        )
        asset.status = AssetStatus.not_recovered


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
    synchronize_recovery_inventory(
        service_id,
        recovery,
        completion,
        db,
    )

    db.commit()
    db.refresh(recovery)
    return recovery
