"""add account_types table and account_type_id

Revision ID: e9ec82f6e441
Revises: d31bc73021d1
Create Date: 2026-07-25 02:12:51.550843

"""
import uuid

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e9ec82f6e441'
down_revision = 'd31bc73021d1'
branch_labels = None
depends_on = None

# Account types used to be a fixed English enum (see the previous migration for
# the French->English rename). Now each user owns their own free-text list, so
# existing accounts get one AccountType row per distinct value they used,
# labeled in the owning user's locale.
DEFAULT_NAMES = {
    "checking": {"fr": "Courant", "en": "Checking"},
    "savings": {"fr": "Épargne", "en": "Savings"},
    "cash": {"fr": "Espèces", "en": "Cash"},
    "credit_card": {"fr": "Carte de crédit", "en": "Credit card"},
    "investment": {"fr": "Investissement", "en": "Investment"},
    "other": {"fr": "Autre", "en": "Other"},
}


def upgrade():
    op.create_table('account_types',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('user_id', sa.String(length=36), nullable=False),
    sa.Column('name', sa.String(length=60), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('account_types', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_account_types_user_id'), ['user_id'], unique=False)

    with op.batch_alter_table('accounts', schema=None) as batch_op:
        batch_op.add_column(sa.Column('account_type_id', sa.String(length=36), nullable=True))
        batch_op.create_foreign_key('fk_accounts_account_type_id', 'account_types', ['account_type_id'], ['id'])

    connection = op.get_bind()
    metadata = sa.MetaData()
    accounts_t = sa.Table('accounts', metadata, autoload_with=connection)
    users_t = sa.Table('users', metadata, autoload_with=connection)
    account_types_t = sa.Table('account_types', metadata, autoload_with=connection)

    users = connection.execute(sa.select(users_t.c.id, users_t.c.locale)).fetchall()
    for user_id, locale in users:
        locale = locale if locale in ("fr", "en") else "fr"
        rows = connection.execute(
            sa.select(accounts_t.c.id, accounts_t.c.account_type)
            .where(accounts_t.c.user_id == user_id)
        ).fetchall()
        code_to_type_id = {}
        for code in sorted({r.account_type for r in rows if r.account_type}):
            new_id = str(uuid.uuid4())
            name = DEFAULT_NAMES.get(code, {}).get(locale, code)
            connection.execute(account_types_t.insert().values(id=new_id, user_id=user_id, name=name))
            code_to_type_id[code] = new_id
        for account_id, code in rows:
            if code in code_to_type_id:
                connection.execute(
                    accounts_t.update()
                    .where(accounts_t.c.id == account_id)
                    .values(account_type_id=code_to_type_id[code])
                )

    with op.batch_alter_table('accounts', schema=None) as batch_op:
        batch_op.drop_column('account_type')


def downgrade():
    with op.batch_alter_table('accounts', schema=None) as batch_op:
        batch_op.add_column(sa.Column('account_type', sa.VARCHAR(length=30), nullable=True))

    connection = op.get_bind()
    metadata = sa.MetaData()
    accounts_t = sa.Table('accounts', metadata, autoload_with=connection)
    account_types_t = sa.Table('account_types', metadata, autoload_with=connection)

    rows = connection.execute(
        sa.select(accounts_t.c.id, accounts_t.c.account_type_id)
    ).fetchall()
    for account_id, type_id in rows:
        if not type_id:
            continue
        name_row = connection.execute(
            sa.select(account_types_t.c.name).where(account_types_t.c.id == type_id)
        ).first()
        if name_row:
            connection.execute(
                accounts_t.update().where(accounts_t.c.id == account_id).values(account_type=name_row[0])
            )

    with op.batch_alter_table('accounts', schema=None) as batch_op:
        batch_op.drop_constraint('fk_accounts_account_type_id', type_='foreignkey')
        batch_op.drop_column('account_type_id')

    with op.batch_alter_table('account_types', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_account_types_user_id'))

    op.drop_table('account_types')
