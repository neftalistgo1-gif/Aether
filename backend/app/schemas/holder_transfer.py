from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class HolderTransferCreate(BaseModel):
    new_customer_id: UUID
    effective_date: date = Field(default_factory=date.today)
    transferred_by: str = Field(min_length=2, max_length=150)
    reason: str = Field(min_length=3, max_length=1000)
    contract_reference: str | None = Field(
        default=None,
        min_length=1,
        max_length=150,
    )


class ServiceHolderAssignCreate(BaseModel):
    customer_id: UUID
    assigned_by: str = Field(min_length=2, max_length=150)
    reason: str = Field(min_length=3, max_length=1000)


class ServiceHolderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    service_id: UUID
    customer_id: UUID
    start_date: date
    end_date: date | None
    change_reason: str | None


class HolderTransferRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    service_id: UUID
    previous_holder_id: UUID
    new_holder_id: UUID
    previous_customer_id: UUID
    new_customer_id: UUID
    effective_date: date
    transferred_by: str
    reason: str
    contract_reference: str | None
    transferred_at: datetime
