"""Fase 3, etapa 5: alertas por e-mail

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-25
"""

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

UPGRADE = """
CREATE TABLE alertas (
  alerta_id      BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  user_id        TEXT NOT NULL REFERENCES users ON DELETE CASCADE,
  ativo_id       BIGINT NOT NULL REFERENCES ativos ON DELETE CASCADE,
  tipo           TEXT NOT NULL CHECK (tipo IN
                   ('preco_acima','preco_abaixo','variacao_dia','insight')),
  parametro      DOUBLE PRECISION,
  codigo         TEXT,
  ativo          BOOLEAN NOT NULL DEFAULT true,
  ultimo_disparo DATE,
  criado_em      TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK ((tipo = 'insight') = (codigo IS NOT NULL)),
  CHECK (tipo = 'insight' OR parametro > 0)
);
CREATE INDEX alertas_user_idx ON alertas (user_id);
CREATE INDEX alertas_ativo_idx ON alertas (ativo_id) WHERE ativo;

CREATE TABLE alertas_disparos (
  alerta_id  BIGINT NOT NULL REFERENCES alertas ON DELETE CASCADE,
  data       DATE NOT NULL,
  texto      TEXT NOT NULL,
  enviado_em TIMESTAMPTZ,
  PRIMARY KEY (alerta_id, data)
);
CREATE INDEX alertas_disparos_pendentes_idx ON alertas_disparos (data) WHERE enviado_em IS NULL;
"""

DOWNGRADE = "DROP TABLE IF EXISTS alertas_disparos, alertas;"


def upgrade() -> None:
    op.execute(UPGRADE)


def downgrade() -> None:
    op.execute(DOWNGRADE)
