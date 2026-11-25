"""Fase 3, etapa 1: índices econômicos (CDI, IPCA, Ibovespa) e watchlist

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-25
"""

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

UPGRADE = """
-- cdi: taxa diária em %; ipca: variação mensal em %; ibov: pontos no fechamento.
CREATE TABLE indices (
  serie TEXT NOT NULL CHECK (serie IN ('cdi','ipca','ibov')),
  data  DATE NOT NULL,
  valor DOUBLE PRECISION NOT NULL,
  PRIMARY KEY (serie, data)
);

CREATE TABLE watchlist (
  user_id   TEXT NOT NULL REFERENCES users ON DELETE CASCADE,
  ativo_id  BIGINT NOT NULL REFERENCES ativos ON DELETE CASCADE,
  criado_em TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (user_id, ativo_id)
);
"""

DOWNGRADE = "DROP TABLE IF EXISTS watchlist, indices;"


def upgrade() -> None:
    op.execute(UPGRADE)


def downgrade() -> None:
    op.execute(DOWNGRADE)
