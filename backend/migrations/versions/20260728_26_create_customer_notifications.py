"""Create customer notification records.

Revision ID: 20260728_26
Revises: 20260728_25
Create Date: 2026-07-28
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260728_26"
down_revision: str | None = "20260728_25"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "customer_notifications",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("customer_id", sa.Uuid(), nullable=False),
        sa.Column("service_id", sa.Uuid(), nullable=True),
        sa.Column(
            "channel",
            sa.Enum(
                "whatsapp",
                "sms",
                "email",
                "phone",
                "in_person",
                name="notification_channel",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "purpose",
            sa.Enum(
                "suspension_warning",
                "payment_reminder",
                "service_update",
                "general",
                name="notification_purpose",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "delivered",
                "failed",
                name="notification_status",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("recipient", sa.String(length=254), nullable=False),
        sa.Column("message_summary", sa.String(length=500), nullable=False),
        sa.Column(
            "provider_reference",
            sa.String(length=250),
            nullable=True,
        ),
        sa.Column(
            "evidence_reference",
            sa.String(length=500),
            nullable=True,
        ),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column("recorded_by", sa.String(length=150), nullable=False),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            nullable=False,
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
    for column in (
        "channel",
        "customer_id",
        "purpose",
        "service_id",
        "status",
    ):
        op.create_index(
            op.f(f"ix_customer_notifications_{column}"),
            "customer_notifications",
            [column],
            unique=False,
        )
    op.add_column(
        "suspensions",
        sa.Column("notification_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_suspensions_notification_id_customer_notifications",
        "suspensions",
        "customer_notifications",
        ["notification_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        op.f("ix_suspensions_notification_id"),
        "suspensions",
        ["notification_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_suspensions_notification_id"),
        table_name="suspensions",
    )
    op.drop_constraint(
        "fk_suspensions_notification_id_customer_notifications",
        "suspensions",
        type_="foreignkey",
    )
    op.drop_column("suspensions", "notification_id")
    for column in (
        "status",
        "service_id",
        "purpose",
        "customer_id",
        "channel",
    ):
        op.drop_index(
            op.f(f"ix_customer_notifications_{column}"),
            table_name="customer_notifications",
        )
    op.drop_table("customer_notifications")
