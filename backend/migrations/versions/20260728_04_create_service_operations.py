"""Create suspension, reactivation and cancellation records.

Revision ID: 20260728_04
Revises: 20260728_03
Create Date: 2026-07-28
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260728_04"
down_revision: str | None = "20260728_03"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def network_result_enum() -> sa.Enum:
    return sa.Enum(
        "success",
        "failed",
        "manual",
        name="network_operation_result",
        native_enum=False,
    )


def upgrade() -> None:
    op.create_table(
        "suspensions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("service_id", sa.Uuid(), nullable=False),
        sa.Column("scheduled_for", sa.Date(), nullable=False),
        sa.Column(
            "executed_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("debt_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("grace_period_elapsed", sa.Boolean(), nullable=False),
        sa.Column("extension_checked", sa.Boolean(), nullable=False),
        sa.Column("has_active_extension", sa.Boolean(), nullable=False),
        sa.Column("notification_sent", sa.Boolean(), nullable=False),
        sa.Column(
            "notification_sent_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column("performed_by", sa.String(length=150), nullable=False),
        sa.Column(
            "mikrotik_result",
            network_result_enum(),
            nullable=False,
        ),
        sa.Column("mikrotik_details", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["service_id"],
            ["services.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_suspensions_service_id"),
        "suspensions",
        ["service_id"],
        unique=False,
    )

    op.create_table(
        "reactivations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("suspension_id", sa.Uuid(), nullable=False),
        sa.Column(
            "executed_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("authorized_by", sa.String(length=150), nullable=False),
        sa.Column("performed_by", sa.String(length=150), nullable=False),
        sa.Column("debt_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column(
            "mikrotik_result",
            network_result_enum(),
            nullable=False,
        ),
        sa.Column("mikrotik_details", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["suspension_id"],
            ["suspensions.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_reactivations_suspension_id"),
        "reactivations",
        ["suspension_id"],
        unique=False,
    )

    op.create_table(
        "cancellations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("service_id", sa.Uuid(), nullable=False),
        sa.Column("requester_customer_id", sa.Uuid(), nullable=False),
        sa.Column("requested_at", sa.Date(), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("folio", sa.String(length=40), nullable=False),
        sa.Column("pending_balance", sa.Numeric(12, 2), nullable=False),
        sa.Column("credit_balance", sa.Numeric(12, 2), nullable=False),
        sa.Column(
            "equipment_recovery_status",
            sa.Enum(
                "pending",
                "scheduled",
                "partial",
                "complete",
                "unrecoverable",
                name="equipment_recovery_status",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("equipment_pending_notes", sa.Text(), nullable=True),
        sa.Column("registered_by", sa.String(length=150), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "scheduled",
                "executed",
                name="cancellation_status",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("executed_by", sa.String(length=150), nullable=True),
        sa.Column(
            "executed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["requester_customer_id"],
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
        op.f("ix_cancellations_folio"),
        "cancellations",
        ["folio"],
        unique=True,
    )
    op.create_index(
        op.f("ix_cancellations_requester_customer_id"),
        "cancellations",
        ["requester_customer_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_cancellations_service_id"),
        "cancellations",
        ["service_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_cancellations_service_id"),
        table_name="cancellations",
    )
    op.drop_index(
        op.f("ix_cancellations_requester_customer_id"),
        table_name="cancellations",
    )
    op.drop_index(
        op.f("ix_cancellations_folio"),
        table_name="cancellations",
    )
    op.drop_table("cancellations")
    op.drop_index(
        op.f("ix_reactivations_suspension_id"),
        table_name="reactivations",
    )
    op.drop_table("reactivations")
    op.drop_index(
        op.f("ix_suspensions_service_id"),
        table_name="suspensions",
    )
    op.drop_table("suspensions")
