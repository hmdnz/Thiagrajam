"""update driver and users database models

Revision ID: b482ea71d838
Revises: cd12d8c67623
Create Date: 2026-09-01 21:51:32.173649

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b482ea71d838'
down_revision: Union[str, Sequence[str], None] = 'cd12d8c67623'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
