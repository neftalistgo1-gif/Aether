from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.v1.endpoints.services import find_service_or_404
from app.db.session import get_db
from app.models.asset import (
    Asset,
    AssetAssignment,
    AssetNetworkHistory,
    AssetOwner,
    AssetReturnOutcome,
    AssetStatus,
    AssetType,
)
from app.models.service import ServiceStatus
from app.schemas.asset import (
    AssetAssignmentCreate,
    AssetAssignmentRead,
    AssetAssignmentReturn,
    AssetCreate,
    AssetRead,
    AssetNetworkHistoryRead,
    AssetUpdate,
)

router = APIRouter(prefix="/api/v1", tags=["assets"])

ASSIGNABLE_ASSET_STATUSES = {
    AssetStatus.available,
    AssetStatus.ready_for_reuse,
}


def generate_internal_code() -> str:
    return f"AST-{uuid4().hex[:12].upper()}"


def find_asset_or_404(asset_id: UUID, db: Session) -> Asset:
    asset = db.get(Asset, asset_id)
    if asset is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Asset not found",
        )
    return asset


def commit_asset_change(db: Session, conflict_detail: str) -> None:
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=conflict_detail,
        ) from error


@router.post(
    "/assets",
    response_model=AssetRead,
    status_code=status.HTTP_201_CREATED,
)
def create_asset(
    asset_data: AssetCreate,
    db: Session = Depends(get_db),
) -> Asset:
    initial_status = (
        AssetStatus.available
        if asset_data.owner == AssetOwner.amr
        else AssetStatus.sold_to_customer
    )
    asset = Asset(
        internal_code=generate_internal_code(),
        status=initial_status,
        **asset_data.model_dump(),
    )
    db.add(asset)
    commit_asset_change(
        db,
        "An asset with this serial number or MAC address already exists",
    )
    db.refresh(asset)
    return asset


@router.get("/assets", response_model=list[AssetRead])
def list_assets(
    db: Annotated[Session, Depends(get_db)],
    q: Annotated[
        str | None,
        Query(
            min_length=2,
            max_length=150,
            description="Internal code, description, serial number or MAC",
        ),
    ] = None,
    asset_type: AssetType | None = None,
    asset_status: AssetStatus | None = None,
) -> list[Asset]:
    statement = select(Asset)
    if q:
        escaped_query = (
            q.strip()
            .replace("\\", "\\\\")
            .replace("%", "\\%")
            .replace("_", "\\_")
        )
        pattern = f"%{escaped_query}%"
        statement = statement.where(
            or_(
                Asset.internal_code.ilike(pattern, escape="\\"),
                Asset.description.ilike(pattern, escape="\\"),
                Asset.serial_number.ilike(pattern, escape="\\"),
                Asset.mac_address.ilike(pattern, escape="\\"),
            )
        )
    if asset_type is not None:
        statement = statement.where(Asset.asset_type == asset_type)
    if asset_status is not None:
        statement = statement.where(Asset.status == asset_status)
    return list(
        db.scalars(statement.order_by(Asset.internal_code, Asset.created_at))
    )


@router.get("/assets/{asset_id}", response_model=AssetRead)
def get_asset(
    asset_id: UUID,
    db: Session = Depends(get_db),
) -> Asset:
    return find_asset_or_404(asset_id, db)


@router.get(
    "/assets/{asset_id}/network-history",
    response_model=list[AssetNetworkHistoryRead],
)
def list_asset_network_history(
    asset_id: UUID,
    db: Session = Depends(get_db),
) -> list[AssetNetworkHistory]:
    find_asset_or_404(asset_id, db)
    statement = (
        select(AssetNetworkHistory)
        .where(AssetNetworkHistory.asset_id == asset_id)
        .order_by(AssetNetworkHistory.changed_at.desc(), AssetNetworkHistory.id.desc())
    )
    return list(db.scalars(statement))


@router.patch("/assets/{asset_id}", response_model=AssetRead)
def update_asset(
    asset_id: UUID,
    update: AssetUpdate,
    db: Session = Depends(get_db),
) -> Asset:
    asset = find_asset_or_404(asset_id, db)
    changes = update.model_dump(exclude_unset=True)
    if all(getattr(asset, key) == value for key, value in changes.items()):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The update does not change any asset value",
        )
    for field_name, value in changes.items():
        setattr(asset, field_name, value)
    asset.updated_at = datetime.now(UTC)
    commit_asset_change(
        db,
        "An asset with this serial number or MAC address already exists",
    )
    db.refresh(asset)
    return asset


@router.get(
    "/assets/{asset_id}/assignments",
    response_model=list[AssetAssignmentRead],
)
def list_asset_assignments(
    asset_id: UUID,
    db: Session = Depends(get_db),
) -> list[AssetAssignment]:
    find_asset_or_404(asset_id, db)
    statement = (
        select(AssetAssignment)
        .where(AssetAssignment.asset_id == asset_id)
        .order_by(AssetAssignment.assigned_at, AssetAssignment.id)
    )
    return list(db.scalars(statement))


@router.post(
    "/services/{service_id}/asset-assignments",
    response_model=AssetAssignmentRead,
    status_code=status.HTTP_201_CREATED,
)
def assign_asset(
    service_id: UUID,
    assignment_data: AssetAssignmentCreate,
    db: Session = Depends(get_db),
) -> AssetAssignment:
    service = find_service_or_404(service_id, db)
    if service.status != ServiceStatus.active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Assets can only be assigned to an active service",
        )
    asset = find_asset_or_404(assignment_data.asset_id, db)
    if asset.owner != AssetOwner.amr:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only assets owned by AMR can be assigned",
        )
    if asset.status not in ASSIGNABLE_ASSET_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": "Asset is not available for assignment",
                "current_status": asset.status.value,
                "allowed_statuses": sorted(
                    item.value for item in ASSIGNABLE_ASSET_STATUSES
                ),
            },
        )

    assignment = AssetAssignment(
        asset_id=asset.id,
        service_id=service.id,
        ownership=asset.owner,
        **assignment_data.model_dump(exclude={"asset_id"}),
    )
    asset.status = AssetStatus.assigned
    db.add(assignment)
    commit_asset_change(db, "Asset is already assigned to a service")
    db.refresh(assignment)
    return assignment


@router.get(
    "/services/{service_id}/asset-assignments",
    response_model=list[AssetAssignmentRead],
)
def list_service_asset_assignments(
    service_id: UUID,
    db: Session = Depends(get_db),
    active_only: bool = False,
) -> list[AssetAssignment]:
    find_service_or_404(service_id, db)
    statement = select(AssetAssignment).where(
        AssetAssignment.service_id == service_id
    )
    if active_only:
        statement = statement.where(AssetAssignment.returned_at.is_(None))
    statement = statement.order_by(
        AssetAssignment.assigned_at,
        AssetAssignment.id,
    )
    return list(db.scalars(statement))


@router.post(
    "/services/{service_id}/asset-assignments/{assignment_id}/return",
    response_model=AssetAssignmentRead,
)
def return_asset(
    service_id: UUID,
    assignment_id: UUID,
    return_data: AssetAssignmentReturn,
    db: Session = Depends(get_db),
) -> AssetAssignment:
    find_service_or_404(service_id, db)
    assignment = db.scalar(
        select(AssetAssignment).where(
            AssetAssignment.id == assignment_id,
            AssetAssignment.service_id == service_id,
        )
    )
    if assignment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Asset assignment not found",
        )
    if assignment.returned_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Asset assignment is already closed",
        )

    asset = find_asset_or_404(assignment.asset_id, db)
    assignment.returned_at = datetime.now(UTC)
    assignment.returned_by = return_data.returned_by
    assignment.condition_on_return = return_data.condition_on_return
    assignment.return_outcome = return_data.outcome
    assignment.notes = return_data.notes

    if return_data.outcome == AssetReturnOutcome.recovered:
        asset.status = AssetStatus.quarantine
    elif return_data.outcome == AssetReturnOutcome.not_recovered:
        asset.status = AssetStatus.not_recovered
    else:
        asset.status = AssetStatus.sold_to_customer
        asset.owner = AssetOwner.customer

    db.commit()
    db.refresh(assignment)
    return assignment
