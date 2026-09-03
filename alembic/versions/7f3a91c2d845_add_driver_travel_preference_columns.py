"""add driver travel preference columns

Revision ID: 7f3a91c2d845
Revises: 00cee63f985c
Create Date: 2026-09-04
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "7f3a91c2d845"
down_revision: Union[str, Sequence[str], None] = "00cee63f985c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create PostgreSQL enum types first
    chattiness_enum = sa.Enum(
        "very_talkative",
        "warm_up",
        "quiet",
        name="chattinessenum",
    )

    music_enum = sa.Enum(
        "always_playing",
        "depends_on_mood",
        "no_music",
        name="musicenum",
    )

    smoking_enum = sa.Enum(
        "allowed",
        "outside_breaks",
        "no_smoking",
        name="smokingenum",
    )

    pets_enum = sa.Enum(
        "pet_friendly",
        "case_by_case",
        "no_pets",
        name="petsenum",
    )

    chattiness_enum.create(op.get_bind(), checkfirst=True)
    music_enum.create(op.get_bind(), checkfirst=True)
    smoking_enum.create(op.get_bind(), checkfirst=True)
    pets_enum.create(op.get_bind(), checkfirst=True)

    # Add columns
    op.add_column(
        "driver_profiles",
        sa.Column(
            "chattiness",
            chattiness_enum,
            nullable=True,
        ),
    )

    op.add_column(
        "driver_profiles",
        sa.Column(
            "music",
            music_enum,
            nullable=True,
        ),
    )

    op.add_column(
        "driver_profiles",
        sa.Column(
            "smoking",
            smoking_enum,
            nullable=True,
        ),
    )

    op.add_column(
        "driver_profiles",
        sa.Column(
            "pets",
            pets_enum,
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("driver_profiles", "pets")
    op.drop_column("driver_profiles", "smoking")
    op.drop_column("driver_profiles", "music")
    op.drop_column("driver_profiles", "chattiness")

    # Remove PostgreSQL enum types
    op.execute("DROP TYPE IF EXISTS petsenum")
    op.execute("DROP TYPE IF EXISTS smokingenum")
    op.execute("DROP TYPE IF EXISTS musicenum")
    op.execute("DROP TYPE IF EXISTS chattinessenum")

