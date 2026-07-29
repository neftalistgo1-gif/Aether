"""Create explicit user permissions.

Revision ID: 20260728_24
Revises: 20260728_23
Create Date: 2026-07-28
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260728_24"
down_revision: str | None = "20260728_23"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


CAPABILITIES = (
    "customers.read",
    "customers.write",
    "services.read",
    "services.write",
    "billing.read",
    "billing.write",
    "billing.approve",
    "contracts.read",
    "contracts.write",
    "installations.read",
    "installations.write",
    "assets.read",
    "assets.write",
    "incidents.read",
    "incidents.write",
    "incidents.compensate",
    "network.read",
    "network.control",
    "plans.read",
    "plans.write",
    "audit.read",
)


def upgrade() -> None:
    op.create_table(
        "user_permissions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "capability",
            sa.Enum(
                *CAPABILITIES,
                name="capability",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("granted_by_id", sa.Uuid(), nullable=False),
        sa.Column("reason", sa.String(length=1000), nullable=False),
        sa.Column("granted_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["granted_by_id"],
            ["operator_users.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["operator_users.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "capability",
            name="uq_user_permissions_user_capability",
        ),
    )
    op.create_index(
        op.f("ix_user_permissions_capability"),
        "user_permissions",
        ["capability"],
        unique=False,
    )
    op.create_index(
        op.f("ix_user_permissions_user_id"),
        "user_permissions",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_user_permissions_user_id"),
        table_name="user_permissions",
    )
    op.drop_index(
        op.f("ix_user_permissions_capability"),
        table_name="user_permissions",
    )
    op.drop_table("user_permissions")
