from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.security import current_authenticated_actor
from app.models.audit import AuditEvent

SENSITIVE_KEY_FRAGMENTS = (
    "password",
    "token",
    "secret",
    "credential",
    "document_content",
    "file_content",
)


def json_safe(value):
    if isinstance(value, dict):
        return {
            str(key): (
                "[REDACTED]"
                if any(
                    fragment in str(key).lower()
                    for fragment in SENSITIVE_KEY_FRAGMENTS
                )
                else json_safe(item)
            )
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple, set)):
        return [json_safe(item) for item in value]
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (UUID, Decimal, date, datetime)):
        return str(value)
    return value


def record_audit_event(
    db: Session,
    *,
    actor: str,
    actor_user_id: UUID | None = None,
    action: str,
    entity_type: str,
    entity_id: UUID | str,
    reason: str,
    before_data: dict[str, object] | None = None,
    after_data: dict[str, object] | None = None,
    source_ip: str | None = None,
    device: str | None = None,
) -> AuditEvent:
    authenticated_actor = current_authenticated_actor()
    if authenticated_actor is not None:
        actor = authenticated_actor.display_name
        actor_user_id = authenticated_actor.user_id
        source_ip = source_ip or authenticated_actor.source_ip
        device = device or authenticated_actor.device
    event = AuditEvent(
        actor=actor,
        actor_user_id=actor_user_id,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id),
        reason=reason,
        before_data=json_safe(before_data),
        after_data=json_safe(after_data),
        source_ip=source_ip,
        device=device,
    )
    db.add(event)
    return event
