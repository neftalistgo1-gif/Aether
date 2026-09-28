"""Keep the installation cost printed on each generated contract."""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260915_02"
down_revision: str | Sequence[str] | None = "20260915_01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("contracts", sa.Column("installation_cost_snapshot", sa.Numeric(12, 2), nullable=True))
    op.add_column("contracts", sa.Column("installation_charge_id", sa.Uuid(), nullable=True))
    op.create_foreign_key("fk_contracts_installation_charge", "contracts", "charges", ["installation_charge_id"], ["id"], ondelete="RESTRICT")
    op.create_unique_constraint("uq_contracts_installation_charge", "contracts", ["installation_charge_id"])


def downgrade() -> None:
    op.drop_constraint("uq_contracts_installation_charge", "contracts", type_="unique")
    op.drop_constraint("fk_contracts_installation_charge", "contracts", type_="foreignkey")
    op.drop_column("contracts", "installation_charge_id")
    op.drop_column("contracts", "installation_cost_snapshot")
