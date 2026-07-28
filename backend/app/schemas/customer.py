from datetime import datetime
from typing import Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class CustomerBase(BaseModel):
    full_name: str = Field(min_length=2, max_length=150)
    phones: list[str] = Field(min_length=1)
    email: str | None = Field(default=None, max_length=254)
    notes: str | None = Field(default=None, max_length=1000)


class CustomerCreate(CustomerBase):
    pass


class CustomerUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=150)
    phones: list[str] | None = Field(default=None, min_length=1)
    email: str | None = Field(default=None, max_length=254)
    notes: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def validate_partial_update(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("At least one field must be provided")

        required_fields = ("full_name", "phones")
        for field_name in required_fields:
            if field_name in self.model_fields_set and getattr(self, field_name) is None:
                raise ValueError(f"{field_name} cannot be null")

        return self


class CustomerRead(CustomerBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    registered_at: datetime
