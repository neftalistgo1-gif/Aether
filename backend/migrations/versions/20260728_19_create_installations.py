"""Create installations and schedule history.

Revision ID: 20260728_19
Revises: 20260728_18
Create Date: 2026-07-28
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260728_19"
down_revision: str | None = "20260728_18"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "installations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("service_id", sa.Uuid(), nullable=False),
        sa.Column("charge_id", sa.Uuid(), nullable=True),
        sa.Column(
            "installation_type",
            sa.Enum(
                "installation",
                "reinstallation",
                "address_change",
                name="installation_type",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "coverage_result",
            sa.Enum(
                "viable",
                "special_equipment",
                "out_of_coverage",
                name="coverage_result",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("coverage_checked_by", sa.String(length=150), nullable=False),
        sa.Column("coverage_checked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("special_equipment_notes", sa.Text(), nullable=True),
        sa.Column("scheduled_for", sa.Date(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "scheduled",
                "completed",
                "cancelled",
                name="installation_status",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("cost", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("technicians", sa.JSON(), nullable=True),
        sa.Column("antenna_photos", sa.JSON(), nullable=True),
        sa.Column("modem_photos", sa.JSON(), nullable=True),
        sa.Column("navigation_confirmed", sa.Boolean(), nullable=True),
        sa.Column("navigation_confirmed_by", sa.String(length=150), nullable=True),
        sa.Column("new_address", sa.String(length=250), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("registered_by", sa.String(length=150), nullable=False),
        sa.Column("registered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancellation_reason", sa.Text(), nullable=True),
        sa.CheckConstraint("cost >= 0", name="ck_installations_nonnegative_cost"),
        sa.ForeignKeyConstraint(["charge_id"], ["charges.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["service_id"], ["services.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("charge_id"),
    )
    op.create_index(
        op.f("ix_installations_service_id"),
        "installations",
        ["service_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_installations_status"),
        "installations",
        ["status"],
        unique=False,
    )
    op.create_index(
        "uq_installations_scheduled_service",
        "installations",
        ["service_id"],
        unique=True,
        postgresql_where=sa.text("status = 'scheduled'"),
        sqlite_where=sa.text("status = 'scheduled'"),
    )
    op.create_table(
        "installation_schedule_changes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("installation_id", sa.Uuid(), nullable=False),
        sa.Column("previous_date", sa.Date(), nullable=False),
        sa.Column("new_date", sa.Date(), nullable=False),
        sa.Column("changed_by", sa.String(length=150), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["installation_id"],
            ["installations.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_installation_schedule_changes_installation_id"),
        "installation_schedule_changes",
        ["installation_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_installation_schedule_changes_installation_id"),
        table_name="installation_schedule_changes",
    )
    op.drop_table("installation_schedule_changes")
    op.drop_index(
        "uq_installations_scheduled_service",
        table_name="installations",
    )
    op.drop_index(op.f("ix_installations_status"), table_name="installations")
    op.drop_index(op.f("ix_installations_service_id"), table_name="installations")
    op.drop_table("installations")
