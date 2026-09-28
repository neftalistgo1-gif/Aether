"""Protect manually confirmed service addresses from UISP synchronization."""
from collections.abc import Sequence
from alembic import op
import sqlalchemy as sa

revision: str = "20260914_02"
down_revision: str | None = "20260901_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

def upgrade() -> None:
    op.add_column("services", sa.Column("address_is_manual", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.alter_column("services", "address_is_manual", server_default=None)

def downgrade() -> None:
    op.drop_column("services", "address_is_manual")
