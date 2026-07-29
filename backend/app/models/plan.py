from datetime import UTC, date, datetime
from decimal import Decimal
from enum import Enum
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Enum as SqlEnum,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class PlanStatus(str, Enum):
    active = "active"
    inactive = "inactive"


class Plan(Base):
    __tablename__ = "plans"

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    speed: Mapped[str] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[PlanStatus] = mapped_column(
        SqlEnum(
            PlanStatus,
            name="plan_status",
            native_enum=False,
            validate_strings=True,
        ),
        default=PlanStatus.active,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )
    deactivated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    deactivated_by: Mapped[str | None] = mapped_column(
        String(150),
        nullable=True,
    )
    deactivation_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    prices: Mapped[list["PlanPrice"]] = relationship(
        back_populates="plan",
        cascade="all, delete-orphan",
        order_by="PlanPrice.valid_from",
        lazy="selectin",
    )

    @property
    def current_price(self) -> Decimal | None:
        current = next(
            (price for price in reversed(self.prices) if price.valid_until is None),
            None,
        )
        return current.monthly_price if current else None


class PlanPrice(Base):
    __tablename__ = "plan_prices"
    __table_args__ = (
        CheckConstraint(
            "monthly_price > 0",
            name="ck_plan_prices_positive_price",
        ),
        CheckConstraint(
            "valid_until IS NULL OR valid_until >= valid_from",
            name="ck_plan_prices_valid_period",
        ),
        Index(
            "uq_plan_prices_current_plan",
            "plan_id",
            unique=True,
            postgresql_where=text("valid_until IS NULL"),
            sqlite_where=text("valid_until IS NULL"),
        ),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    plan_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("plans.id", ondelete="CASCADE"),
        index=True,
    )
    monthly_price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    valid_from: Mapped[date] = mapped_column(Date)
    valid_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    changed_by: Mapped[str] = mapped_column(String(150))
    reason: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )

    plan: Mapped[Plan] = relationship(back_populates="prices")
