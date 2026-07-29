from datetime import UTC, datetime
from enum import Enum
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SqlEnum,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class NetworkControlAction(str, Enum):
    suspend = "suspend"
    reactivate = "reactivate"
    reconcile = "reconcile"


class NetworkCommandStatus(str, Enum):
    simulated = "simulated"
    succeeded = "succeeded"
    failed = "failed"


class MikrotikRouter(Base):
    __tablename__ = "mikrotik_routers"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    endpoint_url: Mapped[str] = mapped_column(String(500))
    suspended_address_list: Mapped[str] = mapped_column(String(100))
    credential_key: Mapped[str] = mapped_column(String(50))
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    verify_tls: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )


class NetworkControlCommand(Base):
    __tablename__ = "network_control_commands"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    idempotency_key: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    service_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("services.id", ondelete="RESTRICT"),
        index=True,
    )
    network_assignment_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("network_assignments.id", ondelete="RESTRICT"),
    )
    router_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("mikrotik_routers.id", ondelete="RESTRICT"),
    )
    action: Mapped[NetworkControlAction] = mapped_column(
        SqlEnum(
            NetworkControlAction,
            name="network_control_action",
            native_enum=False,
            validate_strings=True,
        )
    )
    target_ip: Mapped[str] = mapped_column(String(45))
    desired_blocked: Mapped[bool] = mapped_column(Boolean)
    dry_run: Mapped[bool] = mapped_column(Boolean)
    status: Mapped[NetworkCommandStatus] = mapped_column(
        SqlEnum(
            NetworkCommandStatus,
            name="network_command_status",
            native_enum=False,
            validate_strings=True,
        )
    )
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    requested_by: Mapped[str] = mapped_column(String(150))
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    changed_router: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    result_details: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
