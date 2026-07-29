"""Link live network commands to one-time preflights.

Revision ID: 20260729_29
Revises: 20260729_28
Create Date: 2026-07-29
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260729_29"
down_revision: str | None = "20260729_28"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "network_control_commands",
        sa.Column("preflight_command_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_network_control_commands_preflight_command_id",
        "network_control_commands",
        "network_control_commands",
        ["preflight_command_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        op.f("ix_network_control_commands_preflight_command_id"),
        "network_control_commands",
        ["preflight_command_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_network_control_commands_preflight_command_id"),
        table_name="network_control_commands",
    )
    op.drop_constraint(
        "fk_network_control_commands_preflight_command_id",
        "network_control_commands",
        type_="foreignkey",
    )
    op.drop_column("network_control_commands", "preflight_command_id")
