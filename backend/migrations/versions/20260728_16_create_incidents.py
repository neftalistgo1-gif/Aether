"""Create incidents and affected services.

Revision ID: 20260728_16
Revises: 20260728_15
Create Date: 2026-07-28
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260728_16"
down_revision: str | None = "20260728_15"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "incidents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("tower_name", sa.String(length=150), nullable=True),
        sa.Column("access_point_name", sa.String(length=150), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "open",
                "resolved",
                name="incident_status",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("cause", sa.Text(), nullable=True),
        sa.Column("reported_by", sa.String(length=150), nullable=False),
        sa.Column("responsible", sa.String(length=150), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("registered_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "resolved_at IS NULL OR resolved_at >= started_at",
            name="ck_incidents_valid_period",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_incidents_status"),
        "incidents",
        ["status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_incidents_tower_name"),
        "incidents",
        ["tower_name"],
        unique=False,
    )
    op.create_table(
        "incident_service_impacts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("incident_id", sa.Uuid(), nullable=False),
        sa.Column("service_id", sa.Uuid(), nullable=False),
        sa.Column("customer_id", sa.Uuid(), nullable=False),
        sa.Column("affected_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("restored_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "compensation_amount",
            sa.Numeric(precision=12, scale=2),
            nullable=False,
        ),
        sa.Column("compensation_movement_id", sa.Uuid(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["compensation_movement_id"],
            ["credit_movements.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["customer_id"],
            ["customers.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["incident_id"],
            ["incidents.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["service_id"],
            ["services.id"],
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "restored_at IS NULL OR restored_at >= affected_from",
            name="ck_incident_impacts_valid_period",
        ),
        sa.CheckConstraint(
            "compensation_amount >= 0",
            name="ck_incident_impacts_nonnegative_compensation",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("compensation_movement_id"),
        sa.UniqueConstraint(
            "incident_id",
            "service_id",
            name="uq_incident_service_impacts_incident_service",
        ),
    )
    op.create_index(
        op.f("ix_incident_service_impacts_customer_id"),
        "incident_service_impacts",
        ["customer_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_incident_service_impacts_incident_id"),
        "incident_service_impacts",
        ["incident_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_incident_service_impacts_service_id"),
        "incident_service_impacts",
        ["service_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_incident_service_impacts_service_id"),
        table_name="incident_service_impacts",
    )
    op.drop_index(
        op.f("ix_incident_service_impacts_incident_id"),
        table_name="incident_service_impacts",
    )
    op.drop_index(
        op.f("ix_incident_service_impacts_customer_id"),
        table_name="incident_service_impacts",
    )
    op.drop_table("incident_service_impacts")
    op.drop_index(op.f("ix_incidents_tower_name"), table_name="incidents")
    op.drop_index(op.f("ix_incidents_status"), table_name="incidents")
    op.drop_table("incidents")
