"""add reviewed to transactions

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-08-26 09:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd4e5f6a7b8c9'
down_revision = 'c3d4e5f6a7b8'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('transactions', schema=None) as batch_op:
        batch_op.add_column(sa.Column('reviewed', sa.Boolean(), nullable=True))

    connection = op.get_bind()
    metadata = sa.MetaData()
    transactions_t = sa.Table('transactions', metadata, autoload_with=connection)
    connection.execute(transactions_t.update().values(reviewed=False))


def downgrade():
    with op.batch_alter_table('transactions', schema=None) as batch_op:
        batch_op.drop_column('reviewed')
