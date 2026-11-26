"""Fase 5: WhatsApp pela Evolution API, com a instância cadastrada no /admin

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-26
"""

from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None

UPGRADE = """
-- Uma linha só: a instância da Evolution API que envia os alertas e os códigos.
CREATE TABLE config_whatsapp (
  id             BOOLEAN PRIMARY KEY DEFAULT true CHECK (id),
  url            TEXT NOT NULL,
  instancia      TEXT NOT NULL,
  chave_cifrada  TEXT NOT NULL,
  ativo          BOOLEAN NOT NULL DEFAULT true,
  atualizado_em  TIMESTAMPTZ NOT NULL DEFAULT now(),
  atualizado_por TEXT REFERENCES users ON DELETE SET NULL
);
"""

DOWNGRADE = "DROP TABLE IF EXISTS config_whatsapp;"


def upgrade() -> None:
    op.execute(UPGRADE)


def downgrade() -> None:
    op.execute(DOWNGRADE)
