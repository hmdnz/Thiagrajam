"""payment 2a settlement lifecycle

Revision ID: 08cdc26b056e
Revises: 89776fcdfc80
Create Date: 2026-10-10 15:05:03.086461

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "08cdc26b056e"
down_revision: Union[str, Sequence[str], None] = "89776fcdfc80"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    # ------------------------------------------------------------
    # 1. Settlement status enum
    # ------------------------------------------------------------
    settlement_status_enum = sa.Enum(
        "held",
        "eligible_for_settlement",
        "settled",
        name="settlementstatusenum",
    )

    settlement_status_enum.create(
        op.get_bind(),
        checkfirst=True,
    )

    # ------------------------------------------------------------
    # 2. Payment settlement fields
    # ------------------------------------------------------------
    op.add_column(
        "payments",
        sa.Column(
            "settlement_status",
            settlement_status_enum,
            nullable=True,
        ),
    )

    op.add_column(
        "payments",
        sa.Column(
            "settlement_amount_kobo",
            sa.Integer(),
            nullable=True,
        ),
    )

    op.add_column(
        "payments",
        sa.Column(
            "settlement_eligible_at",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
        ),
    )

    op.add_column(
        "payments",
        sa.Column(
            "settled_at",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
        ),
    )

    op.create_index(
        "ix_payments_settlement_status",
        "payments",
        ["settlement_status"],
        unique=False,
    )

    # ------------------------------------------------------------
    # 3. Balance bucket enum
    # ------------------------------------------------------------
    balance_bucket_enum = sa.Enum(
        "available",
        "pending_earnings",
        name="balancebucketenum",
    )

    balance_bucket_enum.create(
        op.get_bind(),
        checkfirst=True,
    )

    # ------------------------------------------------------------
    # 4. Transaction balance bucket
    # ------------------------------------------------------------
    op.add_column(
        "transactions",
        sa.Column(
            "balance_bucket",
            balance_bucket_enum,
            nullable=True,
        ),
    )

    op.create_index(
        "ix_transactions_balance_bucket",
        "transactions",
        ["balance_bucket"],
        unique=False,
    )

    # ------------------------------------------------------------
    # 5. Pending earnings wallet balance
    # ------------------------------------------------------------
    op.add_column(
        "wallets",
        sa.Column(
            "pending_earnings_balance_kobo",
            sa.Integer(),
            nullable=True,
        ),
    )

    # ------------------------------------------------------------
    # 6. Existing transactions
    #
    # Historical transactions were posted to available balance
    # under the old payment implementation.
    # ------------------------------------------------------------
    op.execute(
        """
        UPDATE transactions
        SET balance_bucket = 'available'
        WHERE balance_bucket IS NULL
        """
    )

    # ------------------------------------------------------------
    # 7. Existing wallets
    # ------------------------------------------------------------
    op.execute(
        """
        UPDATE wallets
        SET pending_earnings_balance_kobo = 0
        WHERE pending_earnings_balance_kobo IS NULL
        """
    )

    # ------------------------------------------------------------
    # 8. Existing successful payments
    #
    # These were already settled by the old implementation.
    # Do NOT move their balances again.
    # ------------------------------------------------------------
    op.execute(
        """
        UPDATE payments
        SET
            settlement_status = 'settled',
            settlement_amount_kobo = amount_kobo,
            settled_at = paid_at
        WHERE status = 'success'
        """
    )

    # ------------------------------------------------------------
    # 9. Existing pending/failed payments
    # ------------------------------------------------------------
    op.execute(
        """
        UPDATE payments
        SET settlement_status = 'held'
        WHERE settlement_status IS NULL
        """
    )

    # ------------------------------------------------------------
    # 10. Make new fields required
    # ------------------------------------------------------------
    op.alter_column(
        "payments",
        "settlement_status",
        nullable=False,
    )

    op.alter_column(
        "transactions",
        "balance_bucket",
        nullable=False,
    )

    op.alter_column(
        "wallets",
        "pending_earnings_balance_kobo",
        nullable=False,
    )


def downgrade() -> None:
    """Downgrade schema."""

    # Wallet
    op.drop_column(
        "wallets",
        "pending_earnings_balance_kobo",
    )

    # Transactions
    op.drop_index(
        "ix_transactions_balance_bucket",
        table_name="transactions",
    )

    op.drop_column(
        "transactions",
        "balance_bucket",
    )

    # Payments
    op.drop_index(
        "ix_payments_settlement_status",
        table_name="payments",
    )

    op.drop_column(
        "payments",
        "settled_at",
    )

    op.drop_column(
        "payments",
        "settlement_eligible_at",
    )

    op.drop_column(
        "payments",
        "settlement_amount_kobo",
    )

    op.drop_column(
        "payments",
        "settlement_status",
    )

    # Enums
    sa.Enum(
        name="balancebucketenum",
    ).drop(
        op.get_bind(),
        checkfirst=True,
    )

    sa.Enum(
        name="settlementstatusenum",
    ).drop(
        op.get_bind(),
        checkfirst=True,
    )