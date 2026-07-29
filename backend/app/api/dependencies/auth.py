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
from app.models.auth import AuthSession, OperatorUser, UserRole

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
