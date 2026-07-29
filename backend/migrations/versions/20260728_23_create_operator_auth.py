"""Create operator authentication.

Revision ID: 20260728_23
Revises: 20260728_22
Create Date: 2026-07-28
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260728_23"
down_revision: str | None = "20260728_22"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "operator_users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("username", sa.String(length=50), nullable=False),
        sa.Column("display_name", sa.String(length=150), nullable=False),
        sa.Column(
            "role",
            sa.Enum(
                "administrator",
                "customer_service",
                "network_technician",
                "installer",
                "read_only",
                name="user_role",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("password_hash", sa.String(length=300), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_by_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deactivated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["created_by_id"],
            ["operator_users.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_operator_users_is_active"),
        "operator_users",
        ["is_active"],
        unique=False,
    )
    op.create_index(
        op.f("ix_operator_users_role"),
        "operator_users",
        ["role"],
        unique=False,
    )
    op.create_index(
        op.f("ix_operator_users_username"),
        "operator_users",
        ["username"],
        unique=True,
    )
    op.create_table(
        "auth_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_ip", sa.String(length=45), nullable=True),
        sa.Column("device", sa.String(length=250), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["operator_users.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_auth_sessions_expires_at"),
        "auth_sessions",
        ["expires_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_auth_sessions_token_hash"),
        "auth_sessions",
        ["token_hash"],
        unique=True,
    )
    op.create_index(
        op.f("ix_auth_sessions_user_id"),
        "auth_sessions",
        ["user_id"],
        unique=False,
    )
    op.add_column(
        "audit_events",
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_audit_events_actor_user_id_operator_users",
        "audit_events",
        "operator_users",
        ["actor_user_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        op.f("ix_audit_events_actor_user_id"),
        "audit_events",
        ["actor_user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_audit_events_actor_user_id"),
        table_name="audit_events",
    )
    op.drop_constraint(
        "fk_audit_events_actor_user_id_operator_users",
        "audit_events",
        type_="foreignkey",
    )
    op.drop_column("audit_events", "actor_user_id")
    op.drop_index(
        op.f("ix_auth_sessions_user_id"),
        table_name="auth_sessions",
    )
    op.drop_index(
        op.f("ix_auth_sessions_token_hash"),
        table_name="auth_sessions",
    )
    op.drop_index(
        op.f("ix_auth_sessions_expires_at"),
        table_name="auth_sessions",
    )
    op.drop_table("auth_sessions")
    op.drop_index(
        op.f("ix_operator_users_username"),
        table_name="operator_users",
    )
    op.drop_index(
        op.f("ix_operator_users_role"),
        table_name="operator_users",
    )
    op.drop_index(
        op.f("ix_operator_users_is_active"),
        table_name="operator_users",
    )
    op.drop_table("operator_users")
