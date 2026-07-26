"""add budget_month to transactions

Revision ID: 3ddfc746b2b9
Revises: 43fc4d114134
Create Date: 2026-07-26 15:30:55.736425

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '3ddfc746b2b9'
down_revision = '43fc4d114134'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('transactions', schema=None) as batch_op:
        batch_op.add_column(sa.Column('budget_month', sa.Date(), nullable=True))

    # Backfill: budget_month defaults to the 1st of the transaction's own date's
    # month, for every existing row (new/edited transactions can override it going
    # forward, but nothing pre-existing should end up with a null budget_month).
    bind = op.get_bind()
    transactions = sa.table(
        'transactions',
        sa.column('id', sa.String),
        sa.column('date', sa.Date),
        sa.column('budget_month', sa.Date),
    )
    rows = bind.execute(sa.select(transactions.c.id, transactions.c.date)).fetchall()
    for tx_id, tx_date in rows:
        bind.execute(
            transactions.update()
            .where(transactions.c.id == tx_id)
            .values(budget_month=tx_date.replace(day=1))
        )

    with op.batch_alter_table('transactions', schema=None) as batch_op:
        batch_op.alter_column('budget_month', nullable=False)
        batch_op.create_index(batch_op.f('ix_transactions_budget_month'), ['budget_month'], unique=False)


def downgrade():
    with op.batch_alter_table('transactions', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_transactions_budget_month'))
        batch_op.drop_column('budget_month')
