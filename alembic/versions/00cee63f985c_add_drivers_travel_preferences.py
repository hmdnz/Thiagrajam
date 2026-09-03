"""add drivers travel preferences

Revision ID: 00cee63f985c
Revises: b482ea71d838
Create Date: 2026-09-03 23:31:48.214736

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '00cee63f985c'
down_revision: Union[str, Sequence[str], None] = 'b482ea71d838'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
