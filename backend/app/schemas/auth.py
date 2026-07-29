from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.auth import Capability, UserRole


class BootstrapAdminCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str = Field(
        min_length=3,
        max_length=50,
        pattern=r"^[a-zA-Z0-9._-]+$",
    )
    display_name: str = Field(min_length=2, max_length=150)
    password: str = Field(min_length=12, max_length=200)

    @field_validator("username", mode="before")
    @classmethod
    def normalize_username(cls, value: object) -> object:
        return value.strip().lower() if isinstance(value, str) else value

    @field_validator("display_name", mode="before")
    @classmethod
    def strip_display_name(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=1, max_length=200)

    @field_validator("username", mode="before")
    @classmethod
    def normalize_username(cls, value: object) -> object:
        return value.strip().lower() if isinstance(value, str) else value


class UserCreate(BootstrapAdminCreate):
    role: UserRole
    permissions: list[Capability] = Field(default_factory=list)

    @field_validator("permissions")
    @classmethod
    def unique_permissions(
        cls,
        value: list[Capability],
    ) -> list[Capability]:
        if len(value) != len(set(value)):
            raise ValueError("Permissions must not be repeated")
        return value


class UserDeactivate(BaseModel):
    reason: str = Field(min_length=3, max_length=1000)


class UserPasswordReset(BaseModel):
    new_password: str = Field(min_length=12, max_length=200)
    reason: str = Field(min_length=3, max_length=1000)


class UserPermissionReplace(BaseModel):
    permissions: list[Capability] = Field(default_factory=list)
    reason: str = Field(min_length=3, max_length=1000)

    @field_validator("permissions")
    @classmethod
    def unique_permissions(
        cls,
        value: list[Capability],
    ) -> list[Capability]:
        if len(value) != len(set(value)):
            raise ValueError("Permissions must not be repeated")
        return value


class OperatorUserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    username: str
    display_name: str
    role: UserRole
    permissions: list[Capability]
    is_active: bool
    created_by_id: UUID | None
    created_at: datetime
    updated_at: datetime
    deactivated_at: datetime | None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime
    user: OperatorUserRead
