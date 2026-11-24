"""schema inicial da Fase 1: mercado, job e Auth.js

Revision ID: 0001
Revises:
Create Date: 2026-11-24
"""

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

UPGRADE = """
CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE TABLE ativos (
  ativo_id      BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  ticker        TEXT NOT NULL UNIQUE CHECK (ticker ~ '^[A-Z0-9]{4,6}$'),
  nome          TEXT NOT NULL,
  tipo          TEXT NOT NULL CHECK (tipo IN ('acao','fii','etf','bdr')),
  setor         TEXT,
  segmento      TEXT,
  logo_url      TEXT,
  ativo         BOOLEAN NOT NULL DEFAULT true,
  atualizado_em TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ativos_tipo_idx ON ativos (tipo) WHERE ativo;
CREATE INDEX ativos_nome_trgm ON ativos USING GIN (nome gin_trgm_ops);

CREATE TABLE cotacoes_diarias (
  ativo_id            BIGINT NOT NULL REFERENCES ativos ON DELETE CASCADE,
  data                DATE NOT NULL,
  abertura            NUMERIC(14,4) NOT NULL CHECK (abertura > 0),
  maxima              NUMERIC(14,4) NOT NULL CHECK (maxima > 0),
  minima              NUMERIC(14,4) NOT NULL CHECK (minima > 0),
  fechamento          NUMERIC(14,4) NOT NULL CHECK (fechamento > 0),
  fechamento_ajustado NUMERIC(14,4) NOT NULL CHECK (fechamento_ajustado > 0),
  volume              BIGINT NOT NULL CHECK (volume >= 0),
  PRIMARY KEY (ativo_id, data),
  CHECK (maxima >= minima)
);

CREATE TABLE indicadores_diarios (
  ativo_id    BIGINT NOT NULL REFERENCES ativos ON DELETE CASCADE,
  data        DATE NOT NULL,
  mm20 DOUBLE PRECISION, mm50 DOUBLE PRECISION, mm200 DOUBLE PRECISION,
  mme9 DOUBLE PRECISION, rsi14 DOUBLE PRECISION,
  macd DOUBLE PRECISION, macd_sinal DOUBLE PRECISION, macd_hist DOUBLE PRECISION,
  bb_superior DOUBLE PRECISION, bb_inferior DOUBLE PRECISION,
  atr14 DOUBLE PRECISION, vol_media20 DOUBLE PRECISION,
  PRIMARY KEY (ativo_id, data)
);

CREATE TABLE proventos (
  provento_id    BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  ativo_id       BIGINT NOT NULL REFERENCES ativos ON DELETE CASCADE,
  tipo           TEXT NOT NULL CHECK (tipo IN
                   ('dividendo','jcp','rendimento','bonificacao','desdobramento','grupamento')),
  data_com       DATE NOT NULL,
  data_pagamento DATE,
  valor          NUMERIC(18,8) NOT NULL,
  UNIQUE (ativo_id, tipo, data_com)
);
CREATE INDEX proventos_ativo_data_idx ON proventos (ativo_id, data_com DESC);

CREATE TABLE fundamentos (
  ativo_id        BIGINT NOT NULL REFERENCES ativos ON DELETE CASCADE,
  data_referencia DATE NOT NULL,
  pl DOUBLE PRECISION, pvp DOUBLE PRECISION, dy_12m DOUBLE PRECISION,
  roe DOUBLE PRECISION, margem_liquida DOUBLE PRECISION,
  div_liq_ebitda DOUBLE PRECISION, vpa DOUBLE PRECISION, lpa DOUBLE PRECISION,
  valor_mercado NUMERIC(20,2),
  extras JSONB NOT NULL DEFAULT '{}',
  PRIMARY KEY (ativo_id, data_referencia)
);

CREATE TABLE execucoes_job (
  execucao_id   BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  tipo          TEXT NOT NULL CHECK (tipo IN ('eod','backfill','catalogo','fundamentos')),
  iniciado_em   TIMESTAMPTZ NOT NULL DEFAULT now(),
  finalizado_em TIMESTAMPTZ,
  status        TEXT NOT NULL DEFAULT 'rodando'
                  CHECK (status IN ('rodando','ok','parcial','erro')),
  ativos_ok     INT NOT NULL DEFAULT 0,
  ativos_erro   INT NOT NULL DEFAULT 0,
  detalhes      JSONB NOT NULL DEFAULT '{}'
);
CREATE INDEX execucoes_job_iniciado_idx ON execucoes_job (iniciado_em DESC);

-- Auth.js (formato do adapter do Drizzle para Postgres)
CREATE TABLE users (
  id              TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
  name            TEXT,
  email           TEXT UNIQUE,
  "emailVerified" TIMESTAMPTZ,
  image           TEXT,
  password_hash   TEXT,
  plano           TEXT NOT NULL DEFAULT 'free',
  role            TEXT NOT NULL DEFAULT 'user' CHECK (role IN ('user','admin'))
);

CREATE TABLE accounts (
  "userId"            TEXT NOT NULL REFERENCES users (id) ON DELETE CASCADE,
  type                TEXT NOT NULL,
  provider            TEXT NOT NULL,
  "providerAccountId" TEXT NOT NULL,
  refresh_token       TEXT,
  access_token        TEXT,
  expires_at          INTEGER,
  token_type          TEXT,
  scope               TEXT,
  id_token            TEXT,
  session_state       TEXT,
  PRIMARY KEY (provider, "providerAccountId")
);
CREATE INDEX accounts_user_idx ON accounts ("userId");

CREATE TABLE sessions (
  "sessionToken" TEXT PRIMARY KEY,
  "userId"       TEXT NOT NULL REFERENCES users (id) ON DELETE CASCADE,
  expires        TIMESTAMPTZ NOT NULL
);

CREATE TABLE verification_tokens (
  identifier TEXT NOT NULL,
  token      TEXT NOT NULL,
  expires    TIMESTAMPTZ NOT NULL,
  PRIMARY KEY (identifier, token)
);
"""

DOWNGRADE = """
DROP TABLE IF EXISTS verification_tokens, sessions, accounts, users;
DROP TABLE IF EXISTS execucoes_job, fundamentos, proventos, indicadores_diarios,
  cotacoes_diarias, ativos;
"""


def upgrade() -> None:
    op.execute(UPGRADE)


def downgrade() -> None:
    op.execute(DOWNGRADE)
