from datetime import UTC, datetime
from enum import Enum
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SqlEnum,
    ForeignKey,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class UserRole(str, Enum):
    administrator = "administrator"
    customer_service = "customer_service"
    network_technician = "network_technician"
    installer = "installer"
    read_only = "read_only"


class Capability(str, Enum):
    customers_read = "customers.read"
    customers_write = "customers.write"
    services_read = "services.read"
    services_write = "services.write"
    billing_read = "billing.read"
    billing_write = "billing.write"
    billing_approve = "billing.approve"
    contracts_read = "contracts.read"
    contracts_write = "contracts.write"
    installations_read = "installations.read"
    installations_write = "installations.write"
    assets_read = "assets.read"
    assets_write = "assets.write"
    incidents_read = "incidents.read"
    incidents_write = "incidents.write"
    incidents_compensate = "incidents.compensate"
    network_read = "network.read"
    network_control = "network.control"
    plans_read = "plans.read"
    plans_write = "plans.write"
    audit_read = "audit.read"
    operations_read = "operations.read"
    operations_run = "operations.run"


class OperatorUser(Base):
    __tablename__ = "operator_users"

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    username: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        index=True,
    )
    display_name: Mapped[str] = mapped_column(String(150))
    role: Mapped[UserRole] = mapped_column(
        SqlEnum(
            UserRole,
            name="user_role",
            native_enum=False,
            validate_strings=True,
        ),
        index=True,
    )
    password_hash: Mapped[str] = mapped_column(String(300))
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        index=True,
    )
    created_by_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("operator_users.id", ondelete="RESTRICT"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
    deactivated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    permission_grants: Mapped[list["UserPermission"]] = relationship(
        foreign_keys="UserPermission.user_id",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    @property
    def permissions(self) -> list[Capability]:
        return [grant.capability for grant in self.permission_grants]


class UserPermission(Base):
    __tablename__ = "user_permissions"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "capability",
            name="uq_user_permissions_user_capability",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("operator_users.id", ondelete="CASCADE"),
        index=True,
    )
    capability: Mapped[Capability] = mapped_column(
        SqlEnum(
            Capability,
            name="capability",
            native_enum=False,
            validate_strings=True,
        ),
        index=True,
    )
    granted_by_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("operator_users.id", ondelete="RESTRICT"),
    )
    reason: Mapped[str] = mapped_column(String(1000))
    granted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )


class AuthSession(Base):
    __tablename__ = "auth_sessions"

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("operator_users.id", ondelete="CASCADE"),
        index=True,
    )
    token_hash: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        index=True,
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_ip: Mapped[str | None] = mapped_column(
        String(45),
        nullable=True,
    )
    device: Mapped[str | None] = mapped_column(
        String(250),
        nullable=True,
    )
