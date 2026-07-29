"""Create contracts and amendments.

Revision ID: 20260728_22
Revises: 20260728_21
Create Date: 2026-07-28
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260728_22"
down_revision: str | None = "20260728_21"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "contracts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("folio", sa.String(length=40), nullable=False),
        sa.Column("customer_id", sa.Uuid(), nullable=False),
        sa.Column("service_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.String(length=50), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("signed_on", sa.Date(), nullable=True),
        sa.Column("signed_by", sa.String(length=150), nullable=True),
        sa.Column(
            "evidence_kind",
            sa.Enum(
                "physical",
                "private_digital",
                name="contract_evidence_kind",
                native_enum=False,
            ),
            nullable=True,
        ),
        sa.Column("document_reference", sa.String(length=500), nullable=True),
        sa.Column("document_sha256", sa.String(length=64), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "draft",
                "active",
                "terminated",
                "void",
                name="contract_status",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("address_snapshot", sa.String(length=250), nullable=False),
        sa.Column("plan_name_snapshot", sa.String(length=100), nullable=False),
        sa.Column(
            "monthly_price_snapshot",
            sa.Numeric(precision=10, scale=2),
            nullable=False,
        ),
        sa.Column("payment_day_snapshot", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.String(length=150), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("terminated_on", sa.Date(), nullable=True),
        sa.Column(
            "termination_folio",
            sa.String(length=40),
            nullable=True,
        ),
        sa.Column("termination_reason", sa.Text(), nullable=True),
        sa.Column("terminated_by", sa.String(length=150), nullable=True),
        sa.Column(
            "termination_evidence_kind",
            sa.Enum(
                "physical",
                "private_digital",
                name="contract_evidence_kind",
                native_enum=False,
            ),
            nullable=True,
        ),
        sa.Column(
            "termination_document_reference",
            sa.String(length=500),
            nullable=True,
        ),
        sa.Column(
            "termination_document_sha256",
            sa.String(length=64),
            nullable=True,
        ),
        sa.Column("voided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("voided_by", sa.String(length=150), nullable=True),
        sa.Column("void_reason", sa.Text(), nullable=True),
        sa.CheckConstraint(
            (
                "status <> 'terminated' OR "
                "(terminated_on IS NOT NULL AND termination_folio IS NOT NULL)"
            ),
            name="ck_contracts_terminated_data",
        ),
        sa.ForeignKeyConstraint(
            ["customer_id"],
            ["customers.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["service_id"],
            ["services.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("termination_folio"),
    )
    op.create_index(
        op.f("ix_contracts_customer_id"),
        "contracts",
        ["customer_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_contracts_folio"),
        "contracts",
        ["folio"],
        unique=True,
    )
    op.create_index(
        op.f("ix_contracts_service_id"),
        "contracts",
        ["service_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_contracts_status"),
        "contracts",
        ["status"],
        unique=False,
    )
    op.create_index(
        "uq_contracts_active_service",
        "contracts",
        ["service_id"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
        sqlite_where=sa.text("status = 'active'"),
    )
    op.create_table(
        "contract_amendments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("contract_id", sa.Uuid(), nullable=False),
        sa.Column(
            "amendment_type",
            sa.Enum(
                "address_change",
                "plan_change",
                name="contract_amendment_type",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("before_data", sa.JSON(), nullable=False),
        sa.Column("after_data", sa.JSON(), nullable=False),
        sa.Column("evidence_reference", sa.String(length=500), nullable=False),
        sa.Column("amended_by", sa.String(length=150), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["contract_id"],
            ["contracts.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_contract_amendments_contract_id"),
        "contract_amendments",
        ["contract_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_contract_amendments_contract_id"),
        table_name="contract_amendments",
    )
    op.drop_table("contract_amendments")
    op.drop_index(
        "uq_contracts_active_service",
        table_name="contracts",
    )
    op.drop_index(op.f("ix_contracts_status"), table_name="contracts")
    op.drop_index(op.f("ix_contracts_service_id"), table_name="contracts")
    op.drop_index(op.f("ix_contracts_folio"), table_name="contracts")
    op.drop_index(op.f("ix_contracts_customer_id"), table_name="contracts")
    op.drop_table("contracts")
