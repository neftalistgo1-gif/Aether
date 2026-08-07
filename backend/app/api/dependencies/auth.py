from datetime import UTC, datetime

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import (
    AuthenticatedActor,
    hash_session_token,
    reset_authenticated_actor,
    set_authenticated_actor,
)
from app.db.session import get_db
from app.models.auth import AuthSession, Capability, OperatorUser, UserRole

bearer_scheme = HTTPBearer(auto_error=False)


def as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def require_authenticated_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(
        bearer_scheme
    ),
    db: Session = Depends(get_db),
):
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    session = db.scalar(
        select(AuthSession).where(
            AuthSession.token_hash
            == hash_session_token(credentials.credentials)
        )
    )
    now = datetime.now(UTC)
    if (
        session is None
        or session.revoked_at is not None
        or as_utc(session.expires_at) <= now
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session is invalid or expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = db.get(OperatorUser, session.user_id)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User is inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )
    request.state.auth_session_id = session.id
    source_ip = request.client.host if request.client is not None else None
    raw_device = request.headers.get("user-agent")
    device = raw_device[:250] if raw_device is not None else None
    context_token = set_authenticated_actor(
        AuthenticatedActor(
            user_id=user.id,
            display_name=user.display_name,
            source_ip=source_ip,
            device=device,
        )
    )
    try:
        yield user
    finally:
        reset_authenticated_actor(context_token)


def require_administrator(
    user: OperatorUser = Depends(require_authenticated_user),
) -> OperatorUser:
    if user.role != UserRole.administrator:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator role required",
        )
    return user


def capability_for_operation(
    method: str,
    route_path: str,
) -> Capability | None:
    method = method.upper()
    is_read = method in {"GET", "HEAD", "OPTIONS"}

    if route_path.startswith("/api/v1/audit-events"):
        return Capability.audit_read if is_read else None
    if route_path.startswith("/api/v1/support-tickets"):
        return (
            Capability.support_read
            if is_read
            else Capability.support_write
        )
    if route_path.startswith("/api/v1/operations"):
        return (
            Capability.operations_read
            if is_read
            else Capability.operations_run
        )
    if route_path.startswith("/api/v1/notifications"):
        return (
            Capability.notifications_read
            if is_read
            else Capability.notifications_write
        )
    if (
        route_path.endswith("/suspensions/coordinated")
        or route_path.endswith("/reactivations/coordinated")
    ):
        return Capability.network_control if not is_read else None
    if "/cancellation" in route_path:
        return (
            Capability.services_read
            if is_read
            else Capability.services_cancel
        )
    if "/network-control/" in route_path:
        return (
            Capability.network_read
            if is_read
            else Capability.network_control
        )
    if (
        "/network-assignments" in route_path
        or "/network-assignment" in route_path
        or route_path.startswith("/api/v1/mikrotik/routers")
    ):
        return (
            Capability.network_read
            if is_read
            else Capability.network_control
        )
    if "/contracts" in route_path:
        return (
            Capability.contracts_read
            if is_read
            else Capability.contracts_write
        )
    if "/installations" in route_path:
        return (
            Capability.installations_read
            if is_read
            else Capability.installations_write
        )
    if (
        "/assets" in route_path
        or "/asset-assignments" in route_path
        or "/equipment-recovery" in route_path
    ):
        return (
            Capability.assets_read
            if is_read
            else Capability.assets_write
        )
    if route_path.startswith("/api/v1/incidents"):
        if route_path.endswith("/compensation") and not is_read:
            return Capability.incidents_compensate
        return (
            Capability.incidents_read
            if is_read
            else Capability.incidents_write
        )
    if route_path.startswith("/api/v1/plans"):
        return Capability.plans_read if is_read else Capability.plans_write
    if (
        route_path.startswith("/api/v1/payments")
        or route_path.startswith("/api/v1/charges")
        or "/charges" in route_path
        or "/balance" in route_path
        or "/credit-" in route_path
        or "/extensions" in route_path
        or "/payment-agreements" in route_path
    ):
        if (
            not is_read
            and (
                route_path.endswith("/verify")
                or route_path.endswith("/reject")
                or route_path.endswith("/cancel")
                or route_path.endswith("/apply")
                or route_path.endswith("/credit-refunds")
                or (
                    (
                        "/extensions/" in route_path
                        or "/payment-agreements/" in route_path
                    )
                    and route_path.endswith("/fulfill")
                )
            )
        ):
            return Capability.billing_approve
        return (
            Capability.billing_read
            if is_read
            else Capability.billing_write
        )
    if route_path.startswith("/api/v1/customers"):
        return (
            Capability.customers_read
            if is_read
            else Capability.customers_write
        )
    if route_path.startswith("/api/v1/postal-codes"):
        return Capability.services_read if is_read else None
    if route_path.startswith("/api/v1/services"):
        return (
            Capability.services_read
            if is_read
            else Capability.services_write
        )
    return None


def require_authorized_user(
    request: Request,
    user: OperatorUser = Depends(require_authenticated_user),
) -> OperatorUser:
    if user.role == UserRole.administrator:
        return user
    route = request.scope.get("route")
    route_path = getattr(route, "path", None)
    capability = (
        capability_for_operation(request.method, route_path)
        if isinstance(route_path, str)
        else None
    )
    if capability is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operation has no authorization policy",
        )
    if capability not in user.permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Capability required: {capability.value}",
        )
    return user
