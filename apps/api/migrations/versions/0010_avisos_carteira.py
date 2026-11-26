"""Fase 7: avisos sobre a carteira (proventos, data com, DARF, vencimentos)

Revision ID: 0010
Revises: 0009
Create Date: 2026-11-26
"""

from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None

UPGRADE = """
-- Sem linha, todos os avisos ficam ligados (valem os padrões abaixo).
CREATE TABLE avisos_carteira_pref (
  user_id     TEXT PRIMARY KEY REFERENCES users ON DELETE CASCADE,
  proventos   BOOLEAN NOT NULL DEFAULT true,
  data_com    BOOLEAN NOT NULL DEFAULT true,
  darf        BOOLEAN NOT NULL DEFAULT true,
  vencimentos BOOLEAN NOT NULL DEFAULT true
);

CREATE TABLE avisos_carteira (
  aviso_id  BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  user_id   TEXT NOT NULL REFERENCES users ON DELETE CASCADE,
  chave     TEXT NOT NULL,
  tipo      TEXT NOT NULL CHECK (tipo IN ('proventos','data_com','darf','vencimentos')),
  data      DATE NOT NULL,
  texto     TEXT NOT NULL,
  url       TEXT NOT NULL,
  criado_em TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (user_id, chave)
);
CREATE INDEX avisos_carteira_data_idx ON avisos_carteira (data);

CREATE TABLE avisos_carteira_envios (
  aviso_id   BIGINT NOT NULL REFERENCES avisos_carteira ON DELETE CASCADE,
  canal      TEXT NOT NULL CHECK (canal IN ('push','whatsapp')),
  enviado_em TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (aviso_id, canal)
);
"""

DOWNGRADE = "DROP TABLE IF EXISTS avisos_carteira_envios, avisos_carteira, avisos_carteira_pref;"


def upgrade() -> None:
    op.execute(UPGRADE)


def downgrade() -> None:
    op.execute(DOWNGRADE)
