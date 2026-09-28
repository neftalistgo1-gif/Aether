from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class CustomerDocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    customer_id: UUID
    document_type: str
    original_name: str
    media_type: str
    size_bytes: int
    uploaded_by: str
    created_at: datetime
