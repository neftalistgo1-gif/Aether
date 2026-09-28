from datetime import UTC, datetime
import logging

from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request, status
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
logger = logging.getLogger(__name__)


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
    native_session: Annotated[
        str | None,
        Header(alias="X-Aether-Session"),
    ] = None,
):
    # Android's share sheet can pass through browser/proxy layers that remove
    # Authorization. The dedicated header carries the same opaque session
    # token and follows exactly the same database validation below.
    session_tokens: list[str] = []
    if native_session:
        session_tokens.append(native_session)
    if credentials is not None and credentials.scheme.lower() == "bearer":
        session_tokens.append(credentials.credentials)
    if not session_tokens:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    # Validate both candidates independently. Some reverse proxies preserve the
    # dedicated native header while replacing the standard Authorization one.
    token_hashes = {hash_session_token(token) for token in session_tokens}
    session = db.scalar(
        select(AuthSession).where(AuthSession.token_hash.in_(token_hashes))
    )
    now = datetime.now(UTC)
    if (
        session is None
        or session.revoked_at is not None
        or as_utc(session.expires_at) <= now
    ):
        logger.warning(
            "Rejected Aether session for %s; fingerprints=%s; device=%s",
            request.url.path,
            sorted(token_hash[:16] for token_hash in token_hashes),
            (request.headers.get("user-agent") or "unknown")[:80],
        )
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
    if route_path.startswith("/api/v1/mikrotik"):
        return Capability.network_read if is_read else Capability.network_control
    if route_path.startswith("/api/v1/network/"):
        return Capability.network_read if is_read else Capability.network_control
    if route_path.startswith("/api/v1/uisp/"):
        return Capability.network_read if is_read else Capability.network_control
    if (
        "/network-assignments" in route_path
        or "/network-assignment" in route_path
        or route_path.endswith("/network-device")
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
        or route_path.endswith("/recovery-inventory")
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
    if route_path.endswith("/payment-day"):
        return (
            Capability.services_read
            if is_read
            else Capability.services_payment_day_write
        )
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
