"""payment 2a wallet ledger transfers

Revision ID: b4d9e2a71c63
Revises: 08cdc26b056e
Create Date: 2026-10-10
"""

from typing import Sequence, Union

from alembic import op


revision: str = "b4d9e2a71c63"
down_revision: Union[str, Sequence[str], None] = "08cdc26b056e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TYPE transactiontypeenum "
        "ADD VALUE IF NOT EXISTS 'balance_transfer'"
    )

    op.execute(
        "ALTER TYPE balancebucketenum "
        "ADD VALUE IF NOT EXISTS 'pending_payout'"
    )


def downgrade() -> None:
    # PostgreSQL does not safely support removing enum values.
    pass