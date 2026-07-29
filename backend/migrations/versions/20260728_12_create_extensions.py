"""Create payment extensions.

Revision ID: 20260728_12
Revises: 20260728_11
Create Date: 2026-07-28
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260728_12"
down_revision: str | None = "20260728_11"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "extensions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("customer_id", sa.Uuid(), nullable=False),
        sa.Column("service_id", sa.Uuid(), nullable=False),
        sa.Column("original_due_date", sa.Date(), nullable=False),
        sa.Column("promised_date", sa.Date(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("authorized_by", sa.String(length=150), nullable=False),
        sa.Column("evidence_reference", sa.String(length=500), nullable=False),
        sa.Column("authorized_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "status",
            sa.Enum("active", "fulfilled", "expired", "cancelled", name="extension_status", native_enum=False),
            nullable=False,
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_by", sa.String(length=150), nullable=True),
        sa.Column("resolution_reason", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["service_id"], ["services.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_extensions_customer_id"), "extensions", ["customer_id"], unique=False)
    op.create_index(op.f("ix_extensions_service_id"), "extensions", ["service_id"], unique=False)
    op.create_index(op.f("ix_extensions_status"), "extensions", ["status"], unique=False)
    op.create_index(
        "uq_extensions_active_service",
        "extensions",
        ["service_id"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
        sqlite_where=sa.text("status = 'active'"),
    )


def downgrade() -> None:
    op.drop_index("uq_extensions_active_service", table_name="extensions")
    op.drop_index(op.f("ix_extensions_status"), table_name="extensions")
    op.drop_index(op.f("ix_extensions_service_id"), table_name="extensions")
    op.drop_index(op.f("ix_extensions_customer_id"), table_name="extensions")
    op.drop_table("extensions")
