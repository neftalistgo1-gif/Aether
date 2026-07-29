"""Create payments and payment status events.

Revision ID: 20260728_10
Revises: 20260728_09
Create Date: 2026-07-28
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260728_10"
down_revision: str | None = "20260728_09"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def payment_status_enum() -> sa.Enum:
    return sa.Enum(
        "pending",
        "verified",
        "rejected",
        "cancelled",
        name="payment_status",
        native_enum=False,
    )


def upgrade() -> None:
    op.create_table(
        "payments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("customer_id", sa.Uuid(), nullable=False),
        sa.Column("service_id", sa.Uuid(), nullable=True),
        sa.Column("declared_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("confirmed_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column(
            "declared_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "received_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "method",
            sa.Enum(
                "cash",
                "bank_transfer",
                "bank_deposit",
                "card",
                "other",
                name="payment_method",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("reference", sa.String(length=150), nullable=True),
        sa.Column(
            "proof_reference",
            sa.String(length=500),
            nullable=True,
        ),
        sa.Column(
            "origin_account_holder",
            sa.String(length=150),
            nullable=True,
        ),
        sa.Column("status", payment_status_enum(), nullable=False),
        sa.Column("received_by", sa.String(length=150), nullable=False),
        sa.Column("verified_by", sa.String(length=150), nullable=True),
        sa.Column(
            "verified_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column("verification_notes", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "declared_amount > 0",
            name="ck_payments_positive_declared_amount",
        ),
        sa.CheckConstraint(
            "confirmed_amount IS NULL OR confirmed_amount > 0",
            name="ck_payments_positive_confirmed_amount",
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
    )
    op.create_index(
        op.f("ix_payments_customer_id"),
        "payments",
        ["customer_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_payments_reference"),
        "payments",
        ["reference"],
        unique=False,
    )
    op.create_index(
        op.f("ix_payments_service_id"),
        "payments",
        ["service_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_payments_status"),
        "payments",
        ["status"],
        unique=False,
    )

    op.create_table(
        "payment_status_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("payment_id", sa.Uuid(), nullable=False),
        sa.Column("from_status", payment_status_enum(), nullable=True),
        sa.Column("to_status", payment_status_enum(), nullable=False),
        sa.Column("performed_by", sa.String(length=150), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["payment_id"],
            ["payments.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_payment_status_events_payment_id"),
        "payment_status_events",
        ["payment_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_payment_status_events_payment_id"),
        table_name="payment_status_events",
    )
    op.drop_table("payment_status_events")
    op.drop_index(op.f("ix_payments_status"), table_name="payments")
    op.drop_index(op.f("ix_payments_service_id"), table_name="payments")
    op.drop_index(op.f("ix_payments_reference"), table_name="payments")
    op.drop_index(op.f("ix_payments_customer_id"), table_name="payments")
    op.drop_table("payments")
