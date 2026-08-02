"""add user admin role and last login

Revision ID: 9c9daa673a43
Revises: bbecc5f6c6ae
Create Date: 2026-08-02 20:35:31.143781

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9c9daa673a43'
down_revision = 'bbecc5f6c6ae'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('last_login_at', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('is_admin', sa.Boolean(), nullable=True))

    # The very first account ever created (oldest created_at) becomes admin,
    # so an existing install always ends up with exactly one administrator
    # rather than none.
    connection = op.get_bind()
    metadata = sa.MetaData()
    users_t = sa.Table('users', metadata, autoload_with=connection)
    first_user = connection.execute(
        sa.select(users_t.c.id).order_by(users_t.c.created_at.asc()).limit(1)
    ).first()
    if first_user:
        connection.execute(
            users_t.update().where(users_t.c.id == first_user[0]).values(is_admin=True)
        )


def downgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('is_admin')
        batch_op.drop_column('last_login_at')
