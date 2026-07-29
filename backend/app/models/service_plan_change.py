from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ServicePlanChange(Base):
    __tablename__ = "service_plan_changes"
    __table_args__ = (
        CheckConstraint(
            "previous_monthly_price > 0",
            name="ck_service_plan_changes_positive_previous_price",
        ),
        CheckConstraint(
            "new_monthly_price > 0",
            name="ck_service_plan_changes_positive_new_price",
        ),
        Index(
            "ix_service_plan_changes_service_billing_period",
            "service_id",
            "billing_effective_period",
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
    previous_plan_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("plans.id", ondelete="RESTRICT"),
        nullable=True,
    )
    new_plan_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("plans.id", ondelete="RESTRICT"),
        index=True,
    )
    previous_plan_name: Mapped[str] = mapped_column(String(100))
    new_plan_name: Mapped[str] = mapped_column(String(100))
    previous_monthly_price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    new_monthly_price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    requested_on: Mapped[date] = mapped_column(Date)
    billing_effective_period: Mapped[date] = mapped_column(Date, index=True)
    requested_by: Mapped[str] = mapped_column(String(150))
    applied_by: Mapped[str] = mapped_column(String(150))
    reason: Mapped[str] = mapped_column(Text)
    custom_price_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )
