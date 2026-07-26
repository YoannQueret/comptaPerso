"""rename french enum values to english

Revision ID: d31bc73021d1
Revises: a8b376048f60
Create Date: 2026-07-25 02:01:01.989502

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd31bc73021d1'
down_revision = 'a8b376048f60'
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        UPDATE accounts SET account_type = CASE account_type
            WHEN 'courant' THEN 'checking'
            WHEN 'epargne' THEN 'savings'
            WHEN 'especes' THEN 'cash'
            WHEN 'carte_credit' THEN 'credit_card'
            WHEN 'investissement' THEN 'investment'
            WHEN 'autre' THEN 'other'
            ELSE account_type
        END
        """
    )
    op.execute(
        """
        UPDATE categories SET kind = CASE kind
            WHEN 'depense' THEN 'expense'
            WHEN 'recette' THEN 'income'
            WHEN 'les_deux' THEN 'both'
            ELSE kind
        END
        """
    )
    op.execute(
        """
        UPDATE recurring_rules SET periodicity = CASE periodicity
            WHEN 'semaine' THEN 'week'
            WHEN 'mois' THEN 'month'
            WHEN 'trimestre' THEN 'quarter'
            WHEN 'annee' THEN 'year'
            ELSE periodicity
        END
        """
    )


def downgrade():
    op.execute(
        """
        UPDATE accounts SET account_type = CASE account_type
            WHEN 'checking' THEN 'courant'
            WHEN 'savings' THEN 'epargne'
            WHEN 'cash' THEN 'especes'
            WHEN 'credit_card' THEN 'carte_credit'
            WHEN 'investment' THEN 'investissement'
            WHEN 'other' THEN 'autre'
            ELSE account_type
        END
        """
    )
    op.execute(
        """
        UPDATE categories SET kind = CASE kind
            WHEN 'expense' THEN 'depense'
            WHEN 'income' THEN 'recette'
            WHEN 'both' THEN 'les_deux'
            ELSE kind
        END
        """
    )
    op.execute(
        """
        UPDATE recurring_rules SET periodicity = CASE periodicity
            WHEN 'week' THEN 'semaine'
            WHEN 'month' THEN 'mois'
            WHEN 'quarter' THEN 'trimestre'
            WHEN 'year' THEN 'annee'
            ELSE periodicity
        END
        """
    )
