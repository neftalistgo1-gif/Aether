from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AccessPointHealthRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    router_id: UUID
    name: str
    ip_address: str
    mac_address: str | None
    interface_name: str | None
    platform: str | None
    source_note: str | None
    status: str
    observed_identity: str | None = None
    observed_age: str | None = None
    checked_at: datetime
