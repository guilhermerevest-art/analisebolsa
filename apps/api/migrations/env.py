"""Alembic é o único dono do schema (spec, seção 3). As migrations são SQL explícito."""

from alembic import context
from sqlalchemy import create_engine, pool

from app.config import get_settings
from app.db import normalizar_url

config = context.config


def _url() -> str:
    return normalizar_url(config.get_main_option("sqlalchemy.url") or get_settings().database_url)


def run_migrations_offline() -> None:
    context.configure(url=_url(), literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(_url(), poolclass=pool.NullPool)
    with engine.connect() as conn:
        context.configure(connection=conn)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
