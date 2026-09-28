"""Create private customer document records."""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260918_01"
down_revision: str | Sequence[str] | None = "20260915_02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "customer_documents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("customer_id", sa.Uuid(), nullable=False),
        sa.Column("document_type", sa.String(length=40), nullable=False),
        sa.Column("original_name", sa.String(length=180), nullable=False),
        sa.Column("storage_name", sa.String(length=180), nullable=False),
        sa.Column("media_type", sa.String(length=80), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("uploaded_by", sa.String(length=150), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("storage_name"),
    )
    op.create_index(op.f("ix_customer_documents_customer_id"), "customer_documents", ["customer_id"])
    op.create_index(op.f("ix_customer_documents_document_type"), "customer_documents", ["document_type"])


def downgrade() -> None:
    op.drop_index(op.f("ix_customer_documents_document_type"), table_name="customer_documents")
    op.drop_index(op.f("ix_customer_documents_customer_id"), table_name="customer_documents")
    op.drop_table("customer_documents")
