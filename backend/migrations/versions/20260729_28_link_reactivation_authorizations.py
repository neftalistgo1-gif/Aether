"""Link reactivations to commercial authorizations.

Revision ID: 20260729_28
Revises: 20260729_27
Create Date: 2026-07-29
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260729_28"
down_revision: str | None = "20260729_27"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "reactivations",
        sa.Column("extension_id", sa.Uuid(), nullable=True),
    )
    op.add_column(
        "reactivations",
        sa.Column("payment_agreement_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_reactivations_extension_id_extensions",
        "reactivations",
        "extensions",
        ["extension_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_reactivations_payment_agreement_id_payment_agreements",
        "reactivations",
        "payment_agreements",
        ["payment_agreement_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        op.f("ix_reactivations_extension_id"),
        "reactivations",
        ["extension_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_reactivations_payment_agreement_id"),
        "reactivations",
        ["payment_agreement_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_reactivations_payment_agreement_id"),
        table_name="reactivations",
    )
    op.drop_index(
        op.f("ix_reactivations_extension_id"),
        table_name="reactivations",
    )
    op.drop_constraint(
        "fk_reactivations_payment_agreement_id_payment_agreements",
        "reactivations",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_reactivations_extension_id_extensions",
        "reactivations",
        type_="foreignkey",
    )
    op.drop_column("reactivations", "payment_agreement_id")
    op.drop_column("reactivations", "extension_id")
