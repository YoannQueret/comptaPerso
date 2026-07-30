"""add currencies table

Revision ID: bbecc5f6c6ae
Revises: 3ddfc746b2b9
Create Date: 2026-07-30 17:45:18.564004

"""
import uuid

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'bbecc5f6c6ae'
down_revision = '3ddfc746b2b9'
branch_labels = None
depends_on = None

# Currencies used to be a fixed, hardcoded list (Config.DEFAULT_CURRENCIES) with
# no way to turn any of them off. Now each user owns their own list, seeded with
# the same 4 codes but only EUR active by default — except any currency a user's
# existing accounts already use, which is activated too so nothing they already
# rely on silently disappears from selection.
DEFAULT_CODES = ["EUR", "CHF", "USD", "GBP"]


def upgrade():
    op.create_table('currencies',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('user_id', sa.String(length=36), nullable=False),
    sa.Column('code', sa.String(length=3), nullable=False),
    sa.Column('active', sa.Boolean(), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('currencies', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_currencies_user_id'), ['user_id'], unique=False)

    connection = op.get_bind()
    metadata = sa.MetaData()
    users_t = sa.Table('users', metadata, autoload_with=connection)
    accounts_t = sa.Table('accounts', metadata, autoload_with=connection)
    currencies_t = sa.Table('currencies', metadata, autoload_with=connection)

    user_ids = [row[0] for row in connection.execute(sa.select(users_t.c.id)).fetchall()]
    for user_id in user_ids:
        used_codes = {
            row[0] for row in connection.execute(
                sa.select(accounts_t.c.currency).where(accounts_t.c.user_id == user_id)
            ).fetchall()
            if row[0]
        }
        for code in DEFAULT_CODES + sorted(used_codes - set(DEFAULT_CODES)):
            active = code == "EUR" or code in used_codes
            connection.execute(
                currencies_t.insert().values(
                    id=str(uuid.uuid4()), user_id=user_id, code=code, active=active
                )
            )


def downgrade():
    with op.batch_alter_table('currencies', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_currencies_user_id'))

    op.drop_table('currencies')
