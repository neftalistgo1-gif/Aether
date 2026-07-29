"""Create service plan change history.

Revision ID: 20260728_21
Revises: 20260728_20
Create Date: 2026-07-28
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260728_21"
down_revision: str | None = "20260728_20"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "services",
        sa.Column("plan_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_services_plan_id_plans",
        "services",
        "plans",
        ["plan_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        op.f("ix_services_plan_id"),
        "services",
        ["plan_id"],
        unique=False,
    )
    op.create_table(
        "service_plan_changes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("service_id", sa.Uuid(), nullable=False),
        sa.Column("previous_plan_id", sa.Uuid(), nullable=True),
        sa.Column("new_plan_id", sa.Uuid(), nullable=False),
        sa.Column("previous_plan_name", sa.String(length=100), nullable=False),
        sa.Column("new_plan_name", sa.String(length=100), nullable=False),
        sa.Column(
            "previous_monthly_price",
            sa.Numeric(precision=10, scale=2),
            nullable=False,
        ),
        sa.Column(
            "new_monthly_price",
            sa.Numeric(precision=10, scale=2),
            nullable=False,
        ),
        sa.Column("requested_on", sa.Date(), nullable=False),
        sa.Column("billing_effective_period", sa.Date(), nullable=False),
        sa.Column("requested_by", sa.String(length=150), nullable=False),
        sa.Column("applied_by", sa.String(length=150), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("custom_price_reason", sa.Text(), nullable=True),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "new_monthly_price > 0",
            name="ck_service_plan_changes_positive_new_price",
        ),
        sa.CheckConstraint(
            "previous_monthly_price > 0",
            name="ck_service_plan_changes_positive_previous_price",
        ),
        sa.ForeignKeyConstraint(
            ["new_plan_id"],
            ["plans.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["previous_plan_id"],
            ["plans.id"],
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
        op.f("ix_service_plan_changes_billing_effective_period"),
        "service_plan_changes",
        ["billing_effective_period"],
        unique=False,
    )
    op.create_index(
        op.f("ix_service_plan_changes_new_plan_id"),
        "service_plan_changes",
        ["new_plan_id"],
        unique=False,
    )
    op.create_index(
        "ix_service_plan_changes_service_billing_period",
        "service_plan_changes",
        ["service_id", "billing_effective_period"],
        unique=False,
    )
    op.create_index(
        op.f("ix_service_plan_changes_service_id"),
        "service_plan_changes",
        ["service_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_service_plan_changes_service_id"),
        table_name="service_plan_changes",
    )
    op.drop_index(
        "ix_service_plan_changes_service_billing_period",
        table_name="service_plan_changes",
    )
    op.drop_index(
        op.f("ix_service_plan_changes_new_plan_id"),
        table_name="service_plan_changes",
    )
    op.drop_index(
        op.f("ix_service_plan_changes_billing_effective_period"),
        table_name="service_plan_changes",
    )
    op.drop_table("service_plan_changes")
    op.drop_index(op.f("ix_services_plan_id"), table_name="services")
    op.drop_constraint(
        "fk_services_plan_id_plans",
        "services",
        type_="foreignkey",
    )
    op.drop_column("services", "plan_id")
