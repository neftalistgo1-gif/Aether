from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class NetworkAccessPoint(Base):
    __tablename__ = "network_access_points"
    __table_args__ = (
        UniqueConstraint("router_id", "ip_address", name="uq_network_access_points_router_ip"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    router_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("mikrotik_routers.id", ondelete="RESTRICT"), index=True
    )
    name: Mapped[str] = mapped_column(String(150))
    ip_address: Mapped[str] = mapped_column(String(45))
    mac_address: Mapped[str | None] = mapped_column(String(17), nullable=True)
    interface_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    platform: Mapped[str | None] = mapped_column(String(150), nullable=True)
    source_note: Mapped[str | None] = mapped_column(String(250), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC)
    )
