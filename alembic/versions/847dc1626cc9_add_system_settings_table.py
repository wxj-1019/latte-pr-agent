"""add_system_settings_table

Revision ID: 847dc1626cc9
Revises: 9188a6839f09
Create Date: 2026-04-17 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '847dc1626cc9'
down_revision: Union[str, None] = '9188a6839f09'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'system_settings',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('key', sa.String(length=100), nullable=False),
        sa.Column('encrypted_value', sa.Text(), nullable=False, server_default=''),
        sa.Column('category', sa.String(length=50), nullable=False, server_default='general'),
        sa.Column('description', sa.String(length=255), nullable=False, server_default=''),
        sa.Column('updated_at', sa.TIMESTAMP(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('key'),
    )


def downgrade() -> None:
    op.drop_table('system_settings')
