from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.integrations.uisp import UISPReadClient, sync_devices
from app.schemas.uisp import UISPConnectionRead

router = APIRouter(prefix="/api/v1/uisp", tags=["uisp telemetry"])


@router.get("/connection", response_model=UISPConnectionRead)
def test_uisp_connection() -> UISPConnectionRead:
    try:
        result = UISPReadClient().test_connection()
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    return UISPConnectionRead(connected=True, device_count=result.device_count)


@router.post("/sync")
def sync_uisp_telemetry(db: Session = Depends(get_db)) -> dict[str, int]:
    try:
        return sync_devices(db, UISPReadClient().list_devices())
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
