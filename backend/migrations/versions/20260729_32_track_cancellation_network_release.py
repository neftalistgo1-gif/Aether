"""Track verified network release after cancellation.

Revision ID: 20260729_32
Revises: 20260729_31
Create Date: 2026-07-29
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260729_32"
down_revision: str | None = "20260729_31"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "cancellations",
        sa.Column("network_release_command_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "cancellations",
        sa.Column(
            "network_released_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "cancellations",
        sa.Column("network_released_by", sa.String(length=150), nullable=True),
    )
    op.add_column(
        "cancellations",
        sa.Column(
            "network_release_evidence_reference",
            sa.Text(),
            nullable=True,
        ),
    )
    op.create_foreign_key(
        "fk_cancellations_network_release_command_id",
        "cancellations",
        "network_control_commands",
        ["network_release_command_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_unique_constraint(
        "uq_cancellations_network_release_command_id",
        "cancellations",
        ["network_release_command_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_cancellations_network_release_command_id",
        "cancellations",
        type_="unique",
    )
    op.drop_constraint(
        "fk_cancellations_network_release_command_id",
        "cancellations",
        type_="foreignkey",
    )
    op.drop_column("cancellations", "network_release_evidence_reference")
    op.drop_column("cancellations", "network_released_by")
    op.drop_column("cancellations", "network_released_at")
    op.drop_column("cancellations", "network_release_command_id")
