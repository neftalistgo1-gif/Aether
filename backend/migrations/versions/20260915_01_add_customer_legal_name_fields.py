"""Store customer legal names in the fields used by the contract template."""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260915_01"
down_revision: str | None = "20260914_02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("customers", sa.Column("given_names", sa.String(length=80), nullable=True))
    op.add_column("customers", sa.Column("paternal_surname", sa.String(length=60), nullable=True))
    op.add_column("customers", sa.Column("maternal_surname", sa.String(length=60), nullable=True))


def downgrade() -> None:
    op.drop_column("customers", "maternal_surname")
    op.drop_column("customers", "paternal_surname")
    op.drop_column("customers", "given_names")
