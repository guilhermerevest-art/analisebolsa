"""Fase 3, etapa 2: carteiras e operações

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-25
"""

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

UPGRADE = """
CREATE TABLE carteiras (
  carteira_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  user_id     TEXT NOT NULL REFERENCES users ON DELETE CASCADE,
  nome        TEXT NOT NULL CHECK (length(nome) BETWEEN 1 AND 60),
  criado_em   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX carteiras_user_idx ON carteiras (user_id);

CREATE TABLE operacoes (
  operacao_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  carteira_id BIGINT NOT NULL REFERENCES carteiras ON DELETE CASCADE,
  ativo_id    BIGINT NOT NULL REFERENCES ativos,
  tipo        TEXT NOT NULL CHECK (tipo IN ('compra','venda')),
  data        DATE NOT NULL,
  quantidade  NUMERIC(18,4) NOT NULL CHECK (quantidade > 0),
  preco       NUMERIC(14,4) NOT NULL CHECK (preco > 0),
  custos      NUMERIC(14,2) NOT NULL DEFAULT 0 CHECK (custos >= 0),
  criado_em   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX operacoes_carteira_idx ON operacoes (carteira_id, data);
"""

DOWNGRADE = "DROP TABLE IF EXISTS operacoes, carteiras;"


def upgrade() -> None:
    op.execute(UPGRADE)


def downgrade() -> None:
    op.execute(DOWNGRADE)
