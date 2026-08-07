"""Create support tickets for customer service triage.

Revision ID: 20260807_01
Revises: 20260729_33
Create Date: 2026-08-07
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260807_01"
down_revision: str | None = "20260729_33"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def enum(*values: str, name: str) -> sa.Enum:
    return sa.Enum(*values, name=name, native_enum=False)


def upgrade() -> None:
    op.create_table(
        "support_tickets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "customer_id",
            sa.Uuid(),
            sa.ForeignKey("customers.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "service_id",
            sa.Uuid(),
            sa.ForeignKey("services.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column(
            "category",
            enum(
                "service_issue",
                "payment_issue",
                "billing_question",
                "account_data",
                "installation_request",
                "other",
                name="support_ticket_category",
            ),
            nullable=False,
        ),
        sa.Column(
            "priority",
            enum("low", "normal", "high", "urgent", name="support_ticket_priority"),
            nullable=False,
        ),
        sa.Column(
            "status",
            enum(
                "new",
                "triaged",
                "assigned_to_technical",
                "waiting_customer",
                "resolved",
                "closed",
                name="support_ticket_status",
            ),
            nullable=False,
        ),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("evidence_reference", sa.String(length=500), nullable=True),
        sa.Column("reported_by", sa.String(length=150), nullable=False),
        sa.Column("created_by", sa.String(length=150), nullable=False),
        sa.Column(
            "assigned_to",
            enum(
                "customer_service",
                "network_technician",
                "installer",
                name="support_ticket_assignee",
            ),
            nullable=True,
        ),
        sa.Column("classified_by", sa.String(length=150), nullable=True),
        sa.Column("classification_notes", sa.Text(), nullable=True),
        sa.Column("resolution_notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_support_tickets_customer_id"),
        "support_tickets",
        ["customer_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_support_tickets_service_id"),
        "support_tickets",
        ["service_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_support_tickets_status"),
        "support_tickets",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_support_tickets_status"), table_name="support_tickets")
    op.drop_index(op.f("ix_support_tickets_service_id"), table_name="support_tickets")
    op.drop_index(op.f("ix_support_tickets_customer_id"), table_name="support_tickets")
    op.drop_table("support_tickets")
