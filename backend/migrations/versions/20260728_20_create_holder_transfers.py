"""Create holder transfer history.

Revision ID: 20260728_20
Revises: 20260728_19
Create Date: 2026-07-28
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260728_20"
down_revision: str | None = "20260728_19"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "holder_transfers",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("service_id", sa.Uuid(), nullable=False),
        sa.Column("previous_holder_id", sa.Uuid(), nullable=False),
        sa.Column("new_holder_id", sa.Uuid(), nullable=False),
        sa.Column("previous_customer_id", sa.Uuid(), nullable=False),
        sa.Column("new_customer_id", sa.Uuid(), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("transferred_by", sa.String(length=150), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("contract_reference", sa.String(length=150), nullable=True),
        sa.Column(
            "transferred_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.CheckConstraint(
            "previous_customer_id <> new_customer_id",
            name="ck_holder_transfers_different_customers",
        ),
        sa.ForeignKeyConstraint(
            ["new_customer_id"],
            ["customers.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["new_holder_id"],
            ["service_holders.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["previous_customer_id"],
            ["customers.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["previous_holder_id"],
            ["service_holders.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["service_id"],
            ["services.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "new_holder_id",
            name="uq_holder_transfers_new_holder",
        ),
        sa.UniqueConstraint(
            "previous_holder_id",
            name="uq_holder_transfers_previous_holder",
        ),
    )
    op.create_index(
        op.f("ix_holder_transfers_new_customer_id"),
        "holder_transfers",
        ["new_customer_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_holder_transfers_previous_customer_id"),
        "holder_transfers",
        ["previous_customer_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_holder_transfers_service_id"),
        "holder_transfers",
        ["service_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_holder_transfers_service_id"),
        table_name="holder_transfers",
    )
    op.drop_index(
        op.f("ix_holder_transfers_previous_customer_id"),
        table_name="holder_transfers",
    )
    op.drop_index(
        op.f("ix_holder_transfers_new_customer_id"),
        table_name="holder_transfers",
    )
    op.drop_table("holder_transfers")
