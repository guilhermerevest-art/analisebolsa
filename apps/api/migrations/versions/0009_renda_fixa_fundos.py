"""Fase 7: renda fixa e fundos na carteira

Revision ID: 0009
Revises: 0008
Create Date: 2026-11-26
"""

from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None

UPGRADE = """
CREATE TABLE investimentos (
  investimento_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  carteira_id     BIGINT NOT NULL REFERENCES carteiras ON DELETE CASCADE,
  tipo            TEXT NOT NULL
                  CHECK (tipo IN ('cdb','lci_lca','tesouro','debenture','outro_rf','fundo')),
  nome            TEXT NOT NULL,
  indexador       TEXT CHECK (indexador IN ('cdi','prefixado','ipca')),
  -- cdi: % do CDI; prefixado: % ao ano; ipca: % ao ano além do IPCA
  taxa            DOUBLE PRECISION,
  data_aplicacao  DATE NOT NULL,
  valor_aplicado  NUMERIC(14,2) NOT NULL CHECK (valor_aplicado > 0),
  vencimento      DATE,
  isento_ir       BOOLEAN NOT NULL DEFAULT false,
  cnpj            TEXT CHECK (cnpj ~ '^[0-9]{14}$'),
  cotas           NUMERIC(24,8) CHECK (cotas > 0),
  resgate_data    DATE,
  resgate_valor   NUMERIC(14,2) CHECK (resgate_valor >= 0),
  criado_em       TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK ((tipo = 'fundo') = (cnpj IS NOT NULL)),
  CHECK (tipo = 'fundo' OR (indexador IS NOT NULL AND taxa IS NOT NULL)),
  CHECK ((resgate_data IS NULL) = (resgate_valor IS NULL))
);
CREATE INDEX investimentos_carteira_idx ON investimentos (carteira_id);

-- Cotas diárias dos fundos (informe diário da CVM), só dos CNPJs que alguém tem.
CREATE TABLE cotas_fundos (
  cnpj  TEXT NOT NULL,
  data  DATE NOT NULL,
  cota  DOUBLE PRECISION NOT NULL,
  PRIMARY KEY (cnpj, data)
);
"""

DOWNGRADE = "DROP TABLE IF EXISTS cotas_fundos, investimentos;"


def upgrade() -> None:
    op.execute(UPGRADE)


def downgrade() -> None:
    op.execute(DOWNGRADE)
