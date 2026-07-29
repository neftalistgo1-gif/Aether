"""Create service charges.

Revision ID: 20260728_09
Revises: 20260728_08
Create Date: 2026-07-28
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260728_09"
down_revision: str | None = "20260728_08"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "charges",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("customer_id", sa.Uuid(), nullable=False),
        sa.Column("service_id", sa.Uuid(), nullable=False),
        sa.Column(
            "charge_type",
            sa.Enum(
                "installation",
                "monthly",
                "address_change",
                "equipment_sale",
                "additional_service",
                "adjustment",
                "other",
                name="charge_type",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("description", sa.String(length=250), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column(
            "outstanding_balance",
            sa.Numeric(12, 2),
            nullable=False,
        ),
        sa.Column(
            "generated_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("billing_period", sa.Date(), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "partial",
                "paid",
                "cancelled",
                name="charge_status",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("generated_by", sa.String(length=150), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "cancelled_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column("cancelled_by", sa.String(length=150), nullable=True),
        sa.Column("cancellation_reason", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "amount > 0",
            name="ck_charges_positive_amount",
        ),
        sa.CheckConstraint(
            "outstanding_balance >= 0 AND outstanding_balance <= amount",
            name="ck_charges_valid_balance",
        ),
        sa.ForeignKeyConstraint(
            ["customer_id"],
            ["customers.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["service_id"],
            ["services.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "service_id",
            "charge_type",
            "billing_period",
            name="uq_charges_service_type_period",
        ),
    )
    op.create_index(
        op.f("ix_charges_charge_type"),
        "charges",
        ["charge_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_charges_customer_id"),
        "charges",
        ["customer_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_charges_due_date"),
        "charges",
        ["due_date"],
        unique=False,
    )
    op.create_index(
        op.f("ix_charges_service_id"),
        "charges",
        ["service_id"],
        unique=False,
    )
    op.create_index(
        "ix_charges_service_due_date",
        "charges",
        ["service_id", "due_date"],
        unique=False,
    )
    op.create_index(
        op.f("ix_charges_status"),
        "charges",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_charges_status"), table_name="charges")
    op.drop_index(
        "ix_charges_service_due_date",
        table_name="charges",
    )
    op.drop_index(op.f("ix_charges_service_id"), table_name="charges")
    op.drop_index(op.f("ix_charges_due_date"), table_name="charges")
    op.drop_index(op.f("ix_charges_customer_id"), table_name="charges")
    op.drop_index(op.f("ix_charges_charge_type"), table_name="charges")
    op.drop_table("charges")
