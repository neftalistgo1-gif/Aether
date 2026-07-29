"""Create payment allocations and credit movements.

Revision ID: 20260728_11
Revises: 20260728_10
Create Date: 2026-07-28
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260728_11"
down_revision: str | None = "20260728_10"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "payments",
        sa.Column(
            "applied_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "payments",
        sa.Column("applied_by", sa.String(length=150), nullable=True),
    )
    op.add_column(
        "payments",
        sa.Column("application_notes", sa.Text(), nullable=True),
    )

    op.create_table(
        "payment_allocations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("payment_id", sa.Uuid(), nullable=False),
        sa.Column("charge_id", sa.Uuid(), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column(
            "applied_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column("applied_by", sa.String(length=150), nullable=False),
        sa.CheckConstraint(
            "amount > 0",
            name="ck_payment_allocations_positive_amount",
        ),
        sa.ForeignKeyConstraint(
            ["charge_id"],
            ["charges.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["payment_id"],
            ["payments.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_payment_allocations_charge_id"),
        "payment_allocations",
        ["charge_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_payment_allocations_payment_id"),
        "payment_allocations",
        ["payment_id"],
        unique=False,
    )

    op.create_table(
        "credit_movements",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("customer_id", sa.Uuid(), nullable=False),
        sa.Column("service_id", sa.Uuid(), nullable=True),
        sa.Column("payment_id", sa.Uuid(), nullable=True),
        sa.Column("charge_id", sa.Uuid(), nullable=True),
        sa.Column(
            "movement_type",
            sa.Enum(
                "payment_excess",
                "charge_application",
                "refund",
                "authorized_adjustment",
                name="credit_movement_type",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column("performed_by", sa.String(length=150), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "amount <> 0",
            name="ck_credit_movements_nonzero_amount",
        ),
        sa.ForeignKeyConstraint(
            ["charge_id"],
            ["charges.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["customer_id"],
            ["customers.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["payment_id"],
            ["payments.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["service_id"],
            ["services.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "payment_id",
            name="uq_credit_movements_payment_id",
        ),
    )
    op.create_index(
        op.f("ix_credit_movements_charge_id"),
        "credit_movements",
        ["charge_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_credit_movements_customer_id"),
        "credit_movements",
        ["customer_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_credit_movements_movement_type"),
        "credit_movements",
        ["movement_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_credit_movements_service_id"),
        "credit_movements",
        ["service_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_credit_movements_service_id"),
        table_name="credit_movements",
    )
    op.drop_index(
        op.f("ix_credit_movements_movement_type"),
        table_name="credit_movements",
    )
    op.drop_index(
        op.f("ix_credit_movements_customer_id"),
        table_name="credit_movements",
    )
    op.drop_index(
        op.f("ix_credit_movements_charge_id"),
        table_name="credit_movements",
    )
    op.drop_table("credit_movements")
    op.drop_index(
        op.f("ix_payment_allocations_payment_id"),
        table_name="payment_allocations",
    )
    op.drop_index(
        op.f("ix_payment_allocations_charge_id"),
        table_name="payment_allocations",
    )
    op.drop_table("payment_allocations")
    op.drop_column("payments", "application_notes")
    op.drop_column("payments", "applied_by")
    op.drop_column("payments", "applied_at")
