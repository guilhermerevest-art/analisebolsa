"""Mercado: dólar, euro, IFIX, Small Caps, Dividendos, S&P 500 e bitcoin

Revision ID: 0008
Revises: 0007
Create Date: 2026-11-26
"""

from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None

ANTIGAS = "'cdi','ipca','ibov'"
NOVAS = "'dolar','euro','ifix','smll','idiv','sp500','bitcoin'"


def upgrade() -> None:
    op.execute("ALTER TABLE indices DROP CONSTRAINT indices_serie_check")
    todas = f"{ANTIGAS},{NOVAS}"
    op.execute(f"ALTER TABLE indices ADD CONSTRAINT indices_serie_check CHECK (serie IN ({todas}))")


def downgrade() -> None:
    op.execute(f"DELETE FROM indices WHERE serie IN ({NOVAS})")
    op.execute("ALTER TABLE indices DROP CONSTRAINT indices_serie_check")
    op.execute(
        f"ALTER TABLE indices ADD CONSTRAINT indices_serie_check CHECK (serie IN ({ANTIGAS}))"
    )
