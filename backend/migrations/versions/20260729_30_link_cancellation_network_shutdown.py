"""Link cancellations to verified network shutdown commands.

Revision ID: 20260729_30
Revises: 20260729_29
Create Date: 2026-07-29
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260729_30"
down_revision: str | None = "20260729_29"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "cancellations",
        sa.Column("network_command_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_cancellations_network_command_id",
        "cancellations",
        "network_control_commands",
        ["network_command_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_unique_constraint(
        "uq_cancellations_network_command_id",
        "cancellations",
        ["network_command_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_cancellations_network_command_id",
        "cancellations",
        type_="unique",
    )
    op.drop_constraint(
        "fk_cancellations_network_command_id",
        "cancellations",
        type_="foreignkey",
    )
    op.drop_column("cancellations", "network_command_id")
