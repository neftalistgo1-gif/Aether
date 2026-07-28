"""Create service events table.

Revision ID: 20260728_03
Revises: 20260728_02
Create Date: 2026-07-28
"""

from collections.abc import Sequence
from uuid import uuid4

from alembic import op
import sqlalchemy as sa

revision: str = "20260728_03"
down_revision: str | None = "20260728_02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "service_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("service_id", sa.Uuid(), nullable=False),
        sa.Column(
            "event_type",
            sa.Enum(
                "registered",
                "details_updated",
                "status_changed",
                name="service_event_type",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "from_status",
            sa.Enum(
                "pending",
                "active",
                "suspended",
                "cancelled",
                name="service_status",
                native_enum=False,
            ),
            nullable=True,
        ),
        sa.Column(
            "to_status",
            sa.Enum(
                "pending",
                "active",
                "suspended",
                "cancelled",
                name="service_status",
                native_enum=False,
            ),
            nullable=True,
        ),
        sa.Column("changes", sa.JSON(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["service_id"],
            ["services.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_service_events_service_id"),
        "service_events",
        ["service_id"],
        unique=False,
    )

    connection = op.get_bind()
    existing_services = connection.execute(
        sa.text(
            "SELECT id, status, registered_at "
            "FROM services"
        )
    ).mappings()
    service_events = sa.table(
        "service_events",
        sa.column("id", sa.Uuid()),
        sa.column("service_id", sa.Uuid()),
        sa.column("event_type", sa.String()),
        sa.column("from_status", sa.String()),
        sa.column("to_status", sa.String()),
        sa.column("changes", sa.JSON()),
        sa.column("reason", sa.Text()),
        sa.column("occurred_at", sa.DateTime(timezone=True)),
    )

    for service in existing_services:
        connection.execute(
            service_events.insert().values(
                id=uuid4(),
                service_id=service["id"],
                event_type="registered",
                from_status=None,
                to_status=service["status"],
                changes=None,
                reason="History initialized during migration",
                occurred_at=service["registered_at"],
            )
        )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_service_events_service_id"),
        table_name="service_events",
    )
    op.drop_table("service_events")
