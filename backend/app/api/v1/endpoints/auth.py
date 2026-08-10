import hmac
from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies.auth import (
    require_administrator,
    require_authenticated_user,
)
from app.core.config import AETHER_BOOTSTRAP_SECRET, AUTH_SESSION_HOURS
from app.core.security import (
    generate_session_token,
    hash_password,
    verify_password,
)
from app.db.session import get_db
from app.models.auth import (
    AuthSession,
    OperatorUser,
    UserPermission,
    UserRole,
)
from app.schemas.auth import (
    BootstrapAdminCreate,
    LoginRequest,
    OperatorUserRead,
    SessionRevokeResult,
    TokenResponse,
    UserCreate,
    UserDeactivate,
    UserPasswordReset,
    UserPermissionReplace,
    UserUpdate,
)
from app.services.audit import record_audit_event

router = APIRouter(prefix="/api/v1/auth", tags=["authentication"])

DUMMY_PASSWORD_HASH = hash_password("aether-dummy-password-never-used")


@router.get("/bootstrap/status")
def bootstrap_status(db: Session = Depends(get_db)) -> dict[str, bool]:
    total_users = db.scalar(select(func.count()).select_from(OperatorUser)) or 0
    configured = AETHER_BOOTSTRAP_SECRET is not None
    return {
        "configured": configured,
        "completed": total_users > 0,
        "can_bootstrap": configured and total_users == 0,
    }


def create_session(
    user: OperatorUser,
    request: Request,
    db: Session,
) -> tuple[str, AuthSession]:
    token, token_hash = generate_session_token()
    session = AuthSession(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=datetime.now(UTC) + timedelta(hours=AUTH_SESSION_HOURS),
        created_ip=(
            request.client.host
            if request.client is not None
            else None
        ),
        device=(
            request.headers.get("user-agent", "")[:250]
            or None
        ),
    )
    db.add(session)
    return token, session


def token_response(
    token: str,
    session: AuthSession,
    user: OperatorUser,
) -> TokenResponse:
    return TokenResponse(
        access_token=token,
        expires_at=session.expires_at,
        user=OperatorUserRead.model_validate(user),
    )


@router.post(
    "/bootstrap",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
)
def bootstrap_administrator(
    data: BootstrapAdminCreate,
    request: Request,
    bootstrap_secret: str | None = Header(
        default=None,
        alias="X-Aether-Bootstrap",
    ),
    db: Session = Depends(get_db),
) -> TokenResponse:
    if AETHER_BOOTSTRAP_SECRET is None:
        raise HTTPException(
            status_code=503,
            detail="Administrator bootstrap is not configured",
        )
    if bootstrap_secret is None or not hmac.compare_digest(
        bootstrap_secret,
        AETHER_BOOTSTRAP_SECRET,
    ):
        raise HTTPException(status_code=401, detail="Invalid bootstrap secret")
    if db.scalar(select(func.count()).select_from(OperatorUser)) != 0:
        raise HTTPException(
            status_code=409,
            detail="Administrator bootstrap has already been completed",
        )
    user = OperatorUser(
        username=data.username,
        display_name=data.display_name.strip(),
        role=UserRole.administrator,
        password_hash=hash_password(data.password),
    )
    db.add(user)
    try:
        db.flush()
        token, session = create_session(user, request, db)
        db.flush()
        record_audit_event(
            db,
            actor=user.display_name,
            actor_user_id=user.id,
            action="auth.administrator_bootstrapped",
            entity_type="OperatorUser",
            entity_id=user.id,
            reason="Initial administrator created",
            source_ip=session.created_ip,
            device=session.device,
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Username already exists",
        ) from exc
    return token_response(token, session, user)


@router.post("/login", response_model=TokenResponse)
def login(
    data: LoginRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> TokenResponse:
    user = db.scalar(
        select(OperatorUser).where(OperatorUser.username == data.username)
    )
    password_hash = (
        user.password_hash
        if user is not None
        else DUMMY_PASSWORD_HASH
    )
    password_matches = verify_password(data.password, password_hash)
    if user is None or not password_matches or not user.is_active:
        raise HTTPException(
            status_code=401,
            detail="Invalid username or password",
        )
    token, session = create_session(user, request, db)
    db.flush()
    record_audit_event(
        db,
        actor=user.display_name,
        actor_user_id=user.id,
        action="auth.login",
        entity_type="OperatorUser",
        entity_id=user.id,
        reason="Successful login",
        source_ip=session.created_ip,
        device=session.device,
    )
    db.commit()
    return token_response(token, session, user)


@router.get("/me", response_model=OperatorUserRead)
def get_current_profile(
    user: OperatorUser = Depends(require_authenticated_user),
) -> OperatorUser:
    return user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    request: Request,
    user: OperatorUser = Depends(require_authenticated_user),
    db: Session = Depends(get_db),
) -> None:
    session = db.get(AuthSession, request.state.auth_session_id)
    if session is not None and session.revoked_at is None:
        session.revoked_at = datetime.now(UTC)
    record_audit_event(
        db,
        actor=user.display_name,
        action="auth.logout",
        entity_type="OperatorUser",
        entity_id=user.id,
        reason="Session closed by user",
    )
    db.commit()


@router.get("/users", response_model=list[OperatorUserRead])
def list_operator_users(
    _administrator: OperatorUser = Depends(require_administrator),
    db: Session = Depends(get_db),
) -> list[OperatorUser]:
    return list(
        db.scalars(
            select(OperatorUser).order_by(
                OperatorUser.display_name,
                OperatorUser.username,
            )
        )
    )


@router.post(
    "/users",
    response_model=OperatorUserRead,
    status_code=status.HTTP_201_CREATED,
)
def create_operator_user(
    data: UserCreate,
    administrator: OperatorUser = Depends(require_administrator),
    db: Session = Depends(get_db),
) -> OperatorUser:
    user = OperatorUser(
        username=data.username,
        display_name=data.display_name.strip(),
        role=data.role,
        password_hash=hash_password(data.password),
        created_by_id=administrator.id,
    )
    db.add(user)
    try:
        db.flush()
        for capability in data.permissions:
            db.add(
                UserPermission(
                    user_id=user.id,
                    capability=capability,
                    granted_by_id=administrator.id,
                    reason="Permissions assigned when account was created",
                )
            )
        db.flush()
        record_audit_event(
            db,
            actor=administrator.display_name,
            action="auth.user_created",
            entity_type="OperatorUser",
            entity_id=user.id,
            reason=f"Operator created with role {data.role.value}",
            after_data={
                "username": user.username,
                "display_name": user.display_name,
                "role": user.role,
                "permissions": [
                    capability.value
                    for capability in data.permissions
                ],
                "is_active": user.is_active,
            },
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Username already exists",
        ) from exc
    return user


@router.put(
    "/users/{user_id}",
    response_model=OperatorUserRead,
)
def update_operator_user(
    user_id: UUID,
    data: UserUpdate,
    administrator: OperatorUser = Depends(require_administrator),
    db: Session = Depends(get_db),
) -> OperatorUser:
    user = db.get(OperatorUser, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Operator user not found")
    before_data = {
        "username": user.username,
        "display_name": user.display_name,
        "role": user.role.value if hasattr(user.role, "value") else user.role,
    }
    if data.username is not None:
        user.username = data.username
    if data.display_name is not None:
        user.display_name = data.display_name
    if data.role is not None:
        user.role = data.role
    try:
        db.flush()
        after_data = {
            "username": user.username,
            "display_name": user.display_name,
            "role": user.role.value if hasattr(user.role, "value") else user.role,
        }
        record_audit_event(
            db,
            actor=administrator.display_name,
            action="auth.user_updated",
            entity_type="OperatorUser",
            entity_id=user.id,
            reason="Operator account updated from UI",
            before_data=before_data,
            after_data=after_data,
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Username already exists",
        ) from exc
    return user


@router.put(
    "/users/{user_id}/permissions",
    response_model=OperatorUserRead,
)
def replace_operator_permissions(
    user_id: UUID,
    data: UserPermissionReplace,
    administrator: OperatorUser = Depends(require_administrator),
    db: Session = Depends(get_db),
) -> OperatorUser:
    user = db.get(OperatorUser, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Operator user not found")
    before = sorted(capability.value for capability in user.permissions)
    requested = set(data.permissions)
    user.permission_grants[:] = [
        grant
        for grant in user.permission_grants
        if grant.capability in requested
    ]
    current = {grant.capability for grant in user.permission_grants}
    for capability in requested - current:
        user.permission_grants.append(
            UserPermission(
                capability=capability,
                granted_by_id=administrator.id,
                reason=data.reason,
            )
        )
    db.flush()
    after = sorted(capability.value for capability in user.permissions)
    record_audit_event(
        db,
        actor=administrator.display_name,
        action="auth.permissions_replaced",
        entity_type="OperatorUser",
        entity_id=user.id,
        reason=data.reason,
        before_data={"permissions": before},
        after_data={"permissions": after},
    )
    db.commit()
    db.refresh(user)
    return user


@router.post(
    "/users/{user_id}/deactivate",
    response_model=OperatorUserRead,
)
def deactivate_operator_user(
    user_id: UUID,
    data: UserDeactivate,
    administrator: OperatorUser = Depends(require_administrator),
    db: Session = Depends(get_db),
) -> OperatorUser:
    user = db.get(OperatorUser, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Operator user not found")
    if user.id == administrator.id:
        raise HTTPException(
            status_code=409,
            detail="Administrator cannot deactivate the current account",
        )
    if not user.is_active:
        raise HTTPException(status_code=409, detail="User is already inactive")
    user.is_active = False
    user.deactivated_at = datetime.now(UTC)
    db.execute(
        update(AuthSession)
        .where(
            AuthSession.user_id == user.id,
            AuthSession.revoked_at.is_(None),
        )
        .values(revoked_at=datetime.now(UTC))
    )
    record_audit_event(
        db,
        actor=administrator.display_name,
        action="auth.user_deactivated",
        entity_type="OperatorUser",
        entity_id=user.id,
        reason=data.reason,
        before_data={"is_active": True},
        after_data={"is_active": False},
    )
    db.commit()
    return user


@router.post(
    "/users/{user_id}/password",
    response_model=OperatorUserRead,
)
def reset_operator_password(
    user_id: UUID,
    data: UserPasswordReset,
    administrator: OperatorUser = Depends(require_administrator),
    db: Session = Depends(get_db),
) -> OperatorUser:
    user = db.get(OperatorUser, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Operator user not found")
    user.password_hash = hash_password(data.new_password)
    db.execute(
        update(AuthSession)
        .where(
            AuthSession.user_id == user.id,
            AuthSession.revoked_at.is_(None),
        )
        .values(revoked_at=datetime.now(UTC))
    )
    record_audit_event(
        db,
        actor=administrator.display_name,
        action="auth.password_reset",
        entity_type="OperatorUser",
        entity_id=user.id,
        reason=data.reason,
    )
    db.commit()
    return user


@router.post(
    "/users/{user_id}/sessions/revoke-others",
    response_model=SessionRevokeResult,
)
def revoke_other_user_sessions(
    user_id: UUID,
    request: Request,
    administrator: OperatorUser = Depends(require_administrator),
    db: Session = Depends(get_db),
) -> SessionRevokeResult:
    """Close active sessions while preserving the administrator's current one."""
    user = db.get(OperatorUser, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Operator user not found")
    result = db.execute(
        update(AuthSession)
        .where(
            AuthSession.user_id == user.id,
            AuthSession.revoked_at.is_(None),
            AuthSession.id != request.state.auth_session_id,
        )
        .values(revoked_at=datetime.now(UTC))
    )
    record_audit_event(
        db,
        actor=administrator.display_name,
        action="auth.other_sessions_revoked",
        entity_type="OperatorUser",
        entity_id=user.id,
        reason="Other device sessions closed from administrator UI",
        after_data={"revoked_sessions": result.rowcount or 0},
    )
    db.commit()
    return SessionRevokeResult(revoked_sessions=result.rowcount or 0)
