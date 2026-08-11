from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, Index, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class MikrotikTrafficSample(Base):
    __tablename__ = "mikrotik_traffic_samples"
    __table_args__ = (
        Index(
            "ix_mikrotik_traffic_samples_router_interface_captured",
            "router_id",
            "interface_name",
            "captured_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    router_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("mikrotik_routers.id", ondelete="RESTRICT"), index=True
    )
    interface_name: Mapped[str] = mapped_column(String(150), index=True)
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True
    )
    rx_bytes: Mapped[int] = mapped_column(BigInteger)
    tx_bytes: Mapped[int] = mapped_column(BigInteger)
    rx_bps: Mapped[float] = mapped_column(Float, default=0)
    tx_bps: Mapped[float] = mapped_column(Float, default=0)
