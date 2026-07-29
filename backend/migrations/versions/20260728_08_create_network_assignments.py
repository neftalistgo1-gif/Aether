"""Create network assignment history.

Revision ID: 20260728_08
Revises: 20260728_07
Create Date: 2026-07-28
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260728_08"
down_revision: str | None = "20260728_07"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "network_assignments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("service_id", sa.Uuid(), nullable=False),
        sa.Column("router_name", sa.String(length=100), nullable=False),
        sa.Column("ip_address", sa.String(length=45), nullable=False),
        sa.Column("tower_name", sa.String(length=150), nullable=False),
        sa.Column(
            "access_point_name",
            sa.String(length=150),
            nullable=False,
        ),
        sa.Column("antenna_name", sa.String(length=150), nullable=False),
        sa.Column("frequency_mhz", sa.Numeric(8, 3), nullable=True),
        sa.Column("signal_dbm", sa.Numeric(6, 2), nullable=True),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "ended_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column("technician", sa.String(length=150), nullable=False),
        sa.Column("change_reason", sa.Text(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["service_id"],
            ["services.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_network_assignments_service_id"),
        "network_assignments",
        ["service_id"],
        unique=False,
    )
    op.create_index(
        "uq_network_assignments_current_service",
        "network_assignments",
        ["service_id"],
        unique=True,
        postgresql_where=sa.text("ended_at IS NULL"),
        sqlite_where=sa.text("ended_at IS NULL"),
    )
    op.create_index(
        "uq_network_assignments_current_router_ip",
        "network_assignments",
        ["router_name", "ip_address"],
        unique=True,
        postgresql_where=sa.text("ended_at IS NULL"),
        sqlite_where=sa.text("ended_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_network_assignments_current_router_ip",
        table_name="network_assignments",
    )
    op.drop_index(
        "uq_network_assignments_current_service",
        table_name="network_assignments",
    )
    op.drop_index(
        op.f("ix_network_assignments_service_id"),
        table_name="network_assignments",
    )
    op.drop_table("network_assignments")
