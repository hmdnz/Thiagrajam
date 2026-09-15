"""update user table

Revision ID: 725c740fee45
Revises: 7f3a91c2d845
Create Date: 2026-09-15 20:48:07.645286

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '725c740fee45'
down_revision: Union[str, Sequence[str], None] = '7f3a91c2d845'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
