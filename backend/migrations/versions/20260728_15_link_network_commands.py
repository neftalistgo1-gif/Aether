"""Link verified network commands to service operations.

Revision ID: 20260728_15
Revises: 20260728_14
Create Date: 2026-07-28
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260728_15"
down_revision: str | None = "20260728_14"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "suspensions",
        sa.Column("network_command_id", sa.Uuid(), nullable=True),
    )
    op.create_unique_constraint(
        "uq_suspensions_network_command_id",
        "suspensions",
        ["network_command_id"],
    )
    op.create_foreign_key(
        "fk_suspensions_network_command_id",
        "suspensions",
        "network_control_commands",
        ["network_command_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.add_column(
        "reactivations",
        sa.Column("network_command_id", sa.Uuid(), nullable=True),
    )
    op.create_unique_constraint(
        "uq_reactivations_network_command_id",
        "reactivations",
        ["network_command_id"],
    )
    op.create_foreign_key(
        "fk_reactivations_network_command_id",
        "reactivations",
        "network_control_commands",
        ["network_command_id"],
        ["id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_reactivations_network_command_id",
        "reactivations",
        type_="foreignkey",
    )
    op.drop_constraint(
        "uq_reactivations_network_command_id",
        "reactivations",
        type_="unique",
    )
    op.drop_column("reactivations", "network_command_id")
    op.drop_constraint(
        "fk_suspensions_network_command_id",
        "suspensions",
        type_="foreignkey",
    )
    op.drop_constraint(
        "uq_suspensions_network_command_id",
        "suspensions",
        type_="unique",
    )
    op.drop_column("suspensions", "network_command_id")
