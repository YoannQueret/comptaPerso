"""add active to users

Revision ID: f1a2b3c4d5e6
Revises: 9c9daa673a43
Create Date: 2026-08-02 21:10:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f1a2b3c4d5e6'
down_revision = '9c9daa673a43'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('active', sa.Boolean(), nullable=True))

    # Existing accounts are active by default; only future admin action deactivates them.
    connection = op.get_bind()
    metadata = sa.MetaData()
    users_t = sa.Table('users', metadata, autoload_with=connection)
    connection.execute(users_t.update().values(active=True))


def downgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('active')
