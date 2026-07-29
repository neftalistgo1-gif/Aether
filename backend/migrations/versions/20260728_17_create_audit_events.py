"""Create immutable audit events.

Revision ID: 20260728_17
Revises: 20260728_16
Create Date: 2026-07-28
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260728_17"
down_revision: str | None = "20260728_16"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "audit_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("actor", sa.String(length=150), nullable=False),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("entity_type", sa.String(length=100), nullable=False),
        sa.Column("entity_id", sa.String(length=100), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("before_data", sa.JSON(), nullable=True),
        sa.Column("after_data", sa.JSON(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("source_ip", sa.String(length=45), nullable=True),
        sa.Column("device", sa.String(length=250), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in (
        "action",
        "actor",
        "entity_id",
        "entity_type",
        "occurred_at",
    ):
        op.create_index(
            op.f(f"ix_audit_events_{column}"),
            "audit_events",
            [column],
            unique=False,
        )
    op.execute(
        """
        CREATE FUNCTION prevent_audit_event_mutation()
        RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'audit_events are immutable';
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_prevent_audit_event_mutation
        BEFORE UPDATE OR DELETE ON audit_events
        FOR EACH ROW EXECUTE FUNCTION prevent_audit_event_mutation()
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER trg_prevent_audit_event_mutation ON audit_events"
    )
    op.execute("DROP FUNCTION prevent_audit_event_mutation()")
    for column in (
        "occurred_at",
        "entity_type",
        "entity_id",
        "actor",
        "action",
    ):
        op.drop_index(
            op.f(f"ix_audit_events_{column}"),
            table_name="audit_events",
        )
    op.drop_table("audit_events")
