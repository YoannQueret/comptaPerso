"""add account shares table

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-08-09 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c3d4e5f6a7b8'
down_revision = 'b2c3d4e5f6a7'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'account_shares',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('account_id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('permission', sa.String(length=5), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['account_id'], ['accounts.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('account_id', 'user_id', name='uq_account_shares_account_user'),
    )
    with op.batch_alter_table('account_shares', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_account_shares_account_id'), ['account_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_account_shares_user_id'), ['user_id'], unique=False)


def downgrade():
    with op.batch_alter_table('account_shares', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_account_shares_user_id'))
        batch_op.drop_index(batch_op.f('ix_account_shares_account_id'))
    op.drop_table('account_shares')
