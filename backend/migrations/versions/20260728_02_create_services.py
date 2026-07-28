"""Create services and service holders tables.

Revision ID: 20260728_02
Revises: 20260728_01
Create Date: 2026-07-28
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260728_02"
down_revision: str | None = "20260728_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "services",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("amr_code", sa.String(length=9), nullable=False),
        sa.Column("address", sa.String(length=250), nullable=False),
        sa.Column("plan_name", sa.String(length=100), nullable=False),
        sa.Column("monthly_price", sa.Numeric(10, 2), nullable=False),
        sa.Column("payment_day", sa.SmallInteger(), nullable=False),
        sa.Column("grace_days", sa.SmallInteger(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "active",
                "suspended",
                "cancelled",
                name="service_status",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("activation_date", sa.Date(), nullable=True),
        sa.Column("cancellation_date", sa.Date(), nullable=True),
        sa.Column("registered_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "grace_days BETWEEN 0 AND 30",
            name="ck_services_grace_days",
        ),
        sa.CheckConstraint(
            "payment_day BETWEEN 1 AND 28",
            name="ck_services_payment_day",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_services_amr_code"),
        "services",
        ["amr_code"],
        unique=False,
    )
    op.create_index(
        "uq_services_current_amr_code",
        "services",
        ["amr_code"],
        unique=True,
        postgresql_where=sa.text("status <> 'cancelled'"),
        sqlite_where=sa.text("status <> 'cancelled'"),
    )

    op.create_table(
        "service_holders",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("service_id", sa.Uuid(), nullable=False),
        sa.Column("customer_id", sa.Uuid(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("change_reason", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["customer_id"],
            ["customers.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["service_id"],
            ["services.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_service_holders_customer_id"),
        "service_holders",
        ["customer_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_service_holders_service_id"),
        "service_holders",
        ["service_id"],
        unique=False,
    )
    op.create_index(
        "uq_service_holders_current_service",
        "service_holders",
        ["service_id"],
        unique=True,
        postgresql_where=sa.text("end_date IS NULL"),
        sqlite_where=sa.text("end_date IS NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_service_holders_current_service",
        table_name="service_holders",
    )
    op.drop_index(
        op.f("ix_service_holders_service_id"),
        table_name="service_holders",
    )
    op.drop_index(
        op.f("ix_service_holders_customer_id"),
        table_name="service_holders",
    )
    op.drop_table("service_holders")
    op.drop_index("uq_services_current_amr_code", table_name="services")
    op.drop_index(op.f("ix_services_amr_code"), table_name="services")
    op.drop_table("services")
