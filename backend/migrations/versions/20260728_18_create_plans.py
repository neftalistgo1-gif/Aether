"""Create plans and price history.

Revision ID: 20260728_18
Revises: 20260728_17
Create Date: 2026-07-28
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260728_18"
down_revision: str | None = "20260728_17"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "plans",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("speed", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "active",
                "inactive",
                name="plan_status",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deactivated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deactivated_by", sa.String(length=150), nullable=True),
        sa.Column("deactivation_reason", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_plans_name"), "plans", ["name"], unique=True)
    op.create_index(
        op.f("ix_plans_status"),
        "plans",
        ["status"],
        unique=False,
    )
    op.create_table(
        "plan_prices",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("plan_id", sa.Uuid(), nullable=False),
        sa.Column(
            "monthly_price",
            sa.Numeric(precision=12, scale=2),
            nullable=False,
        ),
        sa.Column("valid_from", sa.Date(), nullable=False),
        sa.Column("valid_until", sa.Date(), nullable=True),
        sa.Column("changed_by", sa.String(length=150), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "monthly_price > 0",
            name="ck_plan_prices_positive_price",
        ),
        sa.CheckConstraint(
            "valid_until IS NULL OR valid_until >= valid_from",
            name="ck_plan_prices_valid_period",
        ),
        sa.ForeignKeyConstraint(
            ["plan_id"],
            ["plans.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_plan_prices_plan_id"),
        "plan_prices",
        ["plan_id"],
        unique=False,
    )
    op.create_index(
        "uq_plan_prices_current_plan",
        "plan_prices",
        ["plan_id"],
        unique=True,
        postgresql_where=sa.text("valid_until IS NULL"),
        sqlite_where=sa.text("valid_until IS NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_plan_prices_current_plan",
        table_name="plan_prices",
    )
    op.drop_index(
        op.f("ix_plan_prices_plan_id"),
        table_name="plan_prices",
    )
    op.drop_table("plan_prices")
    op.drop_index(op.f("ix_plans_status"), table_name="plans")
    op.drop_index(op.f("ix_plans_name"), table_name="plans")
    op.drop_table("plans")
