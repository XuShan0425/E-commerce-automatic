"""add_users_table

Revision ID: 3667fdd49cd3
Revises: 45cf37bf0146
Create Date: 2026-06-02 06:02:36.648610

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '3667fdd49cd3'
down_revision: Union[str, Sequence[str], None] = '45cf37bf0146'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """创建 users 表（RBAC 用户与角色）。"""
    op.create_table('users',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('username', sa.String(length=100), nullable=False),
        sa.Column('password_hash', sa.String(length=256), nullable=False),
        sa.Column('role', sa.String(length=20), nullable=False, server_default=sa.text("'operator'")),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_users_username'), 'users', ['username'], unique=True)


def downgrade() -> None:
    """回滚：删除 users 表。"""
    op.drop_index(op.f('ix_users_username'), table_name='users')
    op.drop_table('users')
