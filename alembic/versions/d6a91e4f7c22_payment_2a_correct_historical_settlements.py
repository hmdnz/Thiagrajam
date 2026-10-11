"""Correct historical 2A settlement amounts from legacy ledger data.

Revision ID: d6a91e4f7c22
Revises: b4d9e2a71c63
Create Date: 2026-10-11
"""

from alembic import op
import sqlalchemy as sa


revision = "d6a91e4f7c22"
down_revision = "b4d9e2a71c63"
branch_labels = None
depends_on = None


def upgrade():
    # Historical successful payments were previously backfilled with
    # settlement_amount_kobo = payment.amount_kobo.
    #
    # For driver bookings, the actual settlement amount is the driver's
    # net earnings:
    #
    #   driver gross earnings
    #   - commission
    #   - tax
    #
    # Legacy commission/tax transactions may not have payment_id populated,
    # so booking_id is deliberately used to associate them with the payment.

    connection = op.get_bind()

    connection.execute(
        sa.text(
            """
            UPDATE payments AS p
            SET settlement_amount_kobo = calculated.net_amount_kobo
            FROM (
                SELECT
                    p2.id AS payment_id,
                    (
                        COALESCE(gross.driver_gross_kobo, 0)
                        - COALESCE(comm.commission_kobo, 0)
                        - COALESCE(tax.tax_kobo, 0)
                    ) AS net_amount_kobo
                FROM payments AS p2
                JOIN bookings AS b
                    ON b.id = p2.booking_id
                JOIN rides AS r
                    ON r.id = b.ride_id
                LEFT JOIN (
                    SELECT
                        t.booking_id,
                        t.user_id,
                        SUM(t.amount_kobo) AS driver_gross_kobo
                    FROM transactions AS t
                    WHERE t.transaction_type::text = 'payment'
                      AND t.direction = 'credit'
                      AND t.payment_id IS NOT NULL
                    GROUP BY t.booking_id, t.user_id
                ) AS gross
                    ON gross.booking_id = b.id
                   AND gross.user_id = r.driver_id
                LEFT JOIN (
                    SELECT
                        t.booking_id,
                        t.user_id,
                        SUM(t.amount_kobo) AS commission_kobo
                    FROM transactions AS t
                    WHERE t.transaction_type::text = 'commission'
                      AND t.direction = 'debit'
                    GROUP BY t.booking_id, t.user_id
                ) AS comm
                    ON comm.booking_id = b.id
                   AND comm.user_id = r.driver_id
                LEFT JOIN (
                    SELECT
                        t.booking_id,
                        t.user_id,
                        SUM(t.amount_kobo) AS tax_kobo
                    FROM transactions AS t
                    WHERE t.transaction_type::text = 'tax'
                      AND t.direction = 'debit'
                    GROUP BY t.booking_id, t.user_id
                ) AS tax
                    ON tax.booking_id = b.id
                   AND tax.user_id = r.driver_id
                WHERE p2.status::text = 'success'
                  AND p2.purpose::text = 'booking'
                  AND p2.booking_id IS NOT NULL
                  AND gross.driver_gross_kobo IS NOT NULL
                  AND (
                      COALESCE(gross.driver_gross_kobo, 0)
                      - COALESCE(comm.commission_kobo, 0)
                      - COALESCE(tax.tax_kobo, 0)
                  ) >= 0
            ) AS calculated
            WHERE p.id = calculated.payment_id
            """
        )
    )


def downgrade():
    # This is intentionally irreversible.
    #
    # The corrected settlement amount represents the historical net driver
    # settlement and cannot be safely reconstructed for arbitrary future
    # records from the pre-migration state.
    raise RuntimeError(
        "d6a91e4f7c22 is a data-correction migration and cannot be safely downgraded."
    )
