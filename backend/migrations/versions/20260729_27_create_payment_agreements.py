"""Create flexible payment agreements.

Revision ID: 20260729_27
Revises: 20260728_26
Create Date: 2026-07-29
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260729_27"
down_revision: str | None = "20260728_26"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "payment_agreements",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("folio", sa.String(length=40), nullable=False),
        sa.Column("customer_id", sa.Uuid(), nullable=False),
        sa.Column("service_id", sa.Uuid(), nullable=False),
        sa.Column("terms", sa.Text(), nullable=False),
        sa.Column(
            "promised_amount",
            sa.Numeric(precision=12, scale=2),
            nullable=True,
        ),
        sa.Column("promised_date", sa.Date(), nullable=True),
        sa.Column("installment_count", sa.Integer(), nullable=True),
        sa.Column("authorized_by", sa.String(length=150), nullable=False),
        sa.Column(
            "evidence_reference",
            sa.String(length=500),
            nullable=True,
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "active",
                "fulfilled",
                "cancelled",
                name="payment_agreement_status",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "resolved_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "resolved_by",
            sa.String(length=150),
            nullable=True,
        ),
        sa.Column("resolution_reason", sa.Text(), nullable=True),
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
    for column, unique in (
        ("customer_id", False),
        ("folio", True),
        ("service_id", False),
        ("status", False),
    ):
        op.create_index(
            op.f(f"ix_payment_agreements_{column}"),
            "payment_agreements",
            [column],
            unique=unique,
        )


def downgrade() -> None:
    for column in ("status", "service_id", "folio", "customer_id"):
        op.drop_index(
            op.f(f"ix_payment_agreements_{column}"),
            table_name="payment_agreements",
        )
    op.drop_table("payment_agreements")
