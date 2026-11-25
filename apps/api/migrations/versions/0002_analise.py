"""Fase 2: métricas (screener), insights e cenários

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-25
"""

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

# Percentuais ficam em pontos percentuais (12.5 = 12,5%), como dy_12m e as variações da API.
UPGRADE = """
CREATE TABLE metricas_ativo (
  ativo_id              BIGINT PRIMARY KEY REFERENCES ativos ON DELETE CASCADE,
  data                  DATE NOT NULL,
  preco                 NUMERIC(14,4) NOT NULL,
  var_1d DOUBLE PRECISION, var_1m DOUBLE PRECISION, var_3m DOUBLE PRECISION,
  var_6m DOUBLE PRECISION, var_12m DOUBLE PRECISION, var_ano DOUBLE PRECISION,
  volatilidade_12m      DOUBLE PRECISION,
  drawdown_12m          DOUBLE PRECISION,
  max_52s               NUMERIC(14,4),
  min_52s               NUMERIC(14,4),
  pos_52s               DOUBLE PRECISION,
  dist_mm50             DOUBLE PRECISION,
  dist_mm200            DOUBLE PRECISION,
  rsi14                 DOUBLE PRECISION,
  tendencia             TEXT CHECK (tendencia IN ('alta','baixa','lateral')),
  volume_financeiro_20d NUMERIC(20,2),
  pregoes               INT NOT NULL,
  pl DOUBLE PRECISION, pvp DOUBLE PRECISION, dy_12m DOUBLE PRECISION,
  roe DOUBLE PRECISION, margem_liquida DOUBLE PRECISION, div_liq_ebitda DOUBLE PRECISION,
  valor_mercado         NUMERIC(20,2),
  atualizado_em         TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX metricas_ativo_liquidez_idx ON metricas_ativo (volume_financeiro_20d DESC NULLS LAST);

CREATE TABLE insights (
  ativo_id   BIGINT NOT NULL REFERENCES ativos ON DELETE CASCADE,
  codigo     TEXT NOT NULL,
  data       DATE NOT NULL,
  categoria  TEXT NOT NULL CHECK (categoria IN
               ('tendencia','momento','volatilidade','volume','fundamentos','proventos')),
  tom        TEXT NOT NULL CHECK (tom IN ('positivo','neutro','atencao')),
  prioridade SMALLINT NOT NULL,
  titulo     TEXT NOT NULL,
  texto      TEXT NOT NULL,
  dados      JSONB NOT NULL DEFAULT '{}',
  PRIMARY KEY (ativo_id, codigo)
);
CREATE INDEX insights_codigo_data_idx ON insights (codigo, data DESC);

CREATE TABLE cenarios (
  ativo_id      BIGINT PRIMARY KEY REFERENCES ativos ON DELETE CASCADE,
  data          DATE NOT NULL,
  atr14         DOUBLE PRECISION NOT NULL,
  niveis        JSONB NOT NULL,
  cenarios      JSONB NOT NULL,
  atualizado_em TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE execucoes_job DROP CONSTRAINT execucoes_job_tipo_check;
ALTER TABLE execucoes_job ADD CONSTRAINT execucoes_job_tipo_check
  CHECK (tipo IN ('eod','backfill','catalogo','fundamentos','analise'));
"""

DOWNGRADE = """
DELETE FROM execucoes_job WHERE tipo = 'analise';
ALTER TABLE execucoes_job DROP CONSTRAINT execucoes_job_tipo_check;
ALTER TABLE execucoes_job ADD CONSTRAINT execucoes_job_tipo_check
  CHECK (tipo IN ('eod','backfill','catalogo','fundamentos'));
DROP TABLE IF EXISTS cenarios, insights, metricas_ativo;
"""


def upgrade() -> None:
    op.execute(UPGRADE)


def downgrade() -> None:
    op.execute(DOWNGRADE)
