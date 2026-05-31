"""add_is_tracked_to_products

Revision ID: 45cf37bf0146
Revises:
Create Date: 2026-05-30 17:59:08.356032

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '45cf37bf0146'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('products', sa.Column('is_tracked', sa.Boolean(), server_default=sa.text('false'), nullable=False))


def downgrade() -> None:
    op.drop_column('products', 'is_tracked')
