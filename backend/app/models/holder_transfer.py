from datetime import UTC, date, datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class HolderTransfer(Base):
    __tablename__ = "holder_transfers"
    __table_args__ = (
        CheckConstraint(
            "previous_customer_id <> new_customer_id",
            name="ck_holder_transfers_different_customers",
        ),
        UniqueConstraint(
            "previous_holder_id",
            name="uq_holder_transfers_previous_holder",
        ),
        UniqueConstraint(
            "new_holder_id",
            name="uq_holder_transfers_new_holder",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    service_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("services.id", ondelete="RESTRICT"),
        index=True,
    )
    previous_holder_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("service_holders.id", ondelete="RESTRICT"),
    )
    new_holder_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("service_holders.id", ondelete="RESTRICT"),
    )
    previous_customer_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("customers.id", ondelete="RESTRICT"),
        index=True,
    )
    new_customer_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("customers.id", ondelete="RESTRICT"),
        index=True,
    )
    effective_date: Mapped[date] = mapped_column(Date)
    transferred_by: Mapped[str] = mapped_column(String(150))
    reason: Mapped[str] = mapped_column(Text)
    contract_reference: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True,
    )
    transferred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )
