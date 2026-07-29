from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AuditEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    actor: str
    actor_user_id: UUID | None
    action: str
    entity_type: str
    entity_id: str
    occurred_at: datetime
    before_data: dict[str, object] | None
    after_data: dict[str, object] | None
    reason: str
    source_ip: str | None
    device: str | None
