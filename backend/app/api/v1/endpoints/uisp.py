from fastapi import APIRouter, HTTPException, status

from app.integrations.uisp import UISPReadClient
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
