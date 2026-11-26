"""Fase 5, etapa 1: alertas por push e WhatsApp no lugar do e-mail

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-26
"""

from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None

UPGRADE = """
CREATE TABLE push_inscricoes (
  inscricao_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  user_id      TEXT NOT NULL REFERENCES users ON DELETE CASCADE,
  endpoint     TEXT NOT NULL UNIQUE,
  p256dh       TEXT NOT NULL,
  auth         TEXT NOT NULL,
  aparelho     TEXT,
  criado_em    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX push_inscricoes_user_idx ON push_inscricoes (user_id);

CREATE TABLE whatsapp (
  user_id          TEXT PRIMARY KEY REFERENCES users ON DELETE CASCADE,
  telefone         TEXT NOT NULL,
  confirmado_em    TIMESTAMPTZ,
  ativo            BOOLEAN NOT NULL DEFAULT true,
  codigo_hash      TEXT,
  codigo_expira_em TIMESTAMPTZ,
  tentativas       INT NOT NULL DEFAULT 0,
  codigos_dia      INT NOT NULL DEFAULT 0,
  codigos_data     DATE,
  criado_em        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE alertas_envios (
  alerta_id  BIGINT NOT NULL,
  data       DATE NOT NULL,
  canal      TEXT NOT NULL CHECK (canal IN ('email','push','whatsapp')),
  enviado_em TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (alerta_id, data, canal),
  FOREIGN KEY (alerta_id, data) REFERENCES alertas_disparos ON DELETE CASCADE
);

INSERT INTO alertas_envios (alerta_id, data, canal, enviado_em)
SELECT alerta_id, data, 'email', enviado_em FROM alertas_disparos WHERE enviado_em IS NOT NULL;

DROP INDEX IF EXISTS alertas_disparos_pendentes_idx;
ALTER TABLE alertas_disparos DROP COLUMN enviado_em;
"""

DOWNGRADE = """
ALTER TABLE alertas_disparos ADD COLUMN enviado_em TIMESTAMPTZ;
UPDATE alertas_disparos d SET enviado_em = e.enviado_em
FROM (SELECT alerta_id, data, min(enviado_em) AS enviado_em FROM alertas_envios
      GROUP BY alerta_id, data) e
WHERE e.alerta_id = d.alerta_id AND e.data = d.data;
CREATE INDEX alertas_disparos_pendentes_idx ON alertas_disparos (data) WHERE enviado_em IS NULL;
DROP TABLE IF EXISTS alertas_envios, whatsapp, push_inscricoes;
"""


def upgrade() -> None:
    op.execute(UPGRADE)


def downgrade() -> None:
    op.execute(DOWNGRADE)
