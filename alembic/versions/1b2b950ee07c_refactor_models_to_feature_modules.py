"""refactor_models_to_feature_modules

Revision ID: 1b2b950ee07c
Revises: 725c740fee45
Create Date: 2026-09-15 23:45:43.115492

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1b2b950ee07c'
down_revision: Union[str, Sequence[str], None] = '725c740fee45'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
