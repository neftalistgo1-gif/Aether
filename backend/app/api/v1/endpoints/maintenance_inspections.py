from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.v1.endpoints.equipment_recovery import (
    FINAL_RECOVERY_STATUSES,
    find_cancellation_or_404,
    find_recovery_or_404,
)
from app.api.v1.endpoints.services import find_service_or_404
from app.db.session import get_db
from app.models.asset import Asset, AssetStatus
from app.models.equipment_recovery import EquipmentRecovery
from app.models.maintenance_inspection import (
    InspectionResult,
    MaintenanceInspection,
)
from app.schemas.maintenance_inspection import (
    EquipmentInspectionStatus,
    InspectionState,
    MaintenanceInspectionCreate,
    MaintenanceInspectionRead,
)

router = APIRouter(prefix="/api/v1/services", tags=["maintenance inspections"])

TERMINAL_INSPECTION_RESULTS = {
    InspectionResult.ready_for_reuse,
    InspectionResult.discarded,
}
INSPECTABLE_ASSET_STATUSES = {
    AssetStatus.quarantine,
    AssetStatus.needs_repair,
    AssetStatus.defective,
}
INSPECTION_ASSET_STATUSES = {
    InspectionResult.ready_for_reuse: AssetStatus.ready_for_reuse,
    InspectionResult.needs_repair: AssetStatus.needs_repair,
    InspectionResult.defective: AssetStatus.defective,
    InspectionResult.discarded: AssetStatus.discarded,
}


def get_completed_recovery(
    service_id: UUID,
    db: Session,
) -> EquipmentRecovery:
    find_service_or_404(service_id, db)
    cancellation = find_cancellation_or_404(service_id, db)
    recovery = find_recovery_or_404(cancellation.id, db)
    if recovery.status not in FINAL_RECOVERY_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Equipment recovery must be completed before inspection",
        )
    if not recovery.recovered_equipment:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="There is no recovered equipment to inspect",
        )
    return recovery


def list_recovery_inspections(
    recovery_id: UUID,
    db: Session,
) -> list[MaintenanceInspection]:
    statement = (
        select(MaintenanceInspection)
        .where(
            MaintenanceInspection.equipment_recovery_id == recovery_id
        )
        .order_by(
            MaintenanceInspection.created_at,
            MaintenanceInspection.id,
        )
    )
    return list(db.scalars(statement))


@router.post(
    "/{service_id}/equipment-recovery/inspections",
    response_model=MaintenanceInspectionRead,
    status_code=status.HTTP_201_CREATED,
)
def create_maintenance_inspection(
    service_id: UUID,
    inspection_data: MaintenanceInspectionCreate,
    db: Session = Depends(get_db),
) -> MaintenanceInspection:
    recovery = get_completed_recovery(service_id, db)
    recovered_by_name = {
        item.casefold(): item for item in recovery.recovered_equipment or []
    }
    canonical_equipment_name = recovered_by_name.get(
        inspection_data.equipment_name.casefold()
    )
    if canonical_equipment_name is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only recovered equipment can be inspected",
        )

    asset = db.scalar(
        select(Asset).where(
            Asset.latest_recovery_id == recovery.id,
            func.lower(Asset.recovery_equipment_name)
            == canonical_equipment_name.casefold(),
        )
    )
    if asset is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Recovered equipment has no inventory asset",
        )
    if asset.status not in INSPECTABLE_ASSET_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": "Asset is not available for inspection",
                "current_status": asset.status.value,
            },
        )

    history = list_recovery_inspections(recovery.id, db)
    equipment_history = [
        item
        for item in history
        if item.equipment_name.casefold()
        == canonical_equipment_name.casefold()
    ]
    if (
        equipment_history
        and equipment_history[-1].result in TERMINAL_INSPECTION_RESULTS
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Equipment inspection is closed after it is ready for reuse "
                "or discarded"
            ),
        )

    inspection = MaintenanceInspection(
        equipment_recovery_id=recovery.id,
        asset_id=asset.id,
        **inspection_data.model_dump(exclude={"equipment_name"}),
        equipment_name=canonical_equipment_name,
    )
    if (
        inspection.serial_number
        and asset.serial_number
        and inspection.serial_number != asset.serial_number
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Serial number does not match the inventory asset",
        )
    if (
        inspection.mac_address
        and asset.mac_address
        and inspection.mac_address != asset.mac_address
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="MAC address does not match the inventory asset",
        )
    asset.serial_number = inspection.serial_number or asset.serial_number
    asset.mac_address = inspection.mac_address or asset.mac_address
    asset.model = inspection.model or asset.model
    asset.status = INSPECTION_ASSET_STATUSES[inspection.result]
    db.add(inspection)
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Serial number or MAC address belongs to another asset",
        ) from error
    db.refresh(inspection)
    return inspection


@router.get(
    "/{service_id}/equipment-recovery/inspections",
    response_model=list[MaintenanceInspectionRead],
)
def list_maintenance_inspections(
    service_id: UUID,
    db: Session = Depends(get_db),
) -> list[MaintenanceInspection]:
    recovery = get_completed_recovery(service_id, db)
    return list_recovery_inspections(recovery.id, db)


@router.get(
    "/{service_id}/equipment-recovery/inspection-status",
    response_model=list[EquipmentInspectionStatus],
)
def get_equipment_inspection_status(
    service_id: UUID,
    db: Session = Depends(get_db),
) -> list[EquipmentInspectionStatus]:
    recovery = get_completed_recovery(service_id, db)
    history = list_recovery_inspections(recovery.id, db)
    latest_by_equipment: dict[str, MaintenanceInspection] = {}
    for inspection in history:
        latest_by_equipment[inspection.equipment_name.casefold()] = inspection
    assets_by_equipment = {
        asset.recovery_equipment_name.casefold(): asset
        for asset in db.scalars(
            select(Asset).where(Asset.latest_recovery_id == recovery.id)
        )
        if asset.recovery_equipment_name is not None
    }

    result: list[EquipmentInspectionStatus] = []
    for equipment_name in recovery.recovered_equipment or []:
        latest = latest_by_equipment.get(equipment_name.casefold())
        asset = assets_by_equipment.get(equipment_name.casefold())
        if asset is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Recovered equipment has no inventory asset",
            )
        state = (
            InspectionState(latest.result.value)
            if latest is not None
            else InspectionState.quarantine
        )
        result.append(
            EquipmentInspectionStatus(
                equipment_name=equipment_name,
                asset_id=asset.id,
                internal_code=asset.internal_code,
                state=state,
                reusable=state == InspectionState.ready_for_reuse,
                latest_inspection_id=latest.id if latest else None,
                latest_inspected_at=latest.inspected_at if latest else None,
            )
        )
    return result
