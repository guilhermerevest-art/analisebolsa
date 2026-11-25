"""Conexão com o Postgres (SQLAlchemy 2 core + psycopg 3)."""

import os
from functools import lru_cache

from sqlalchemy import Engine, create_engine, pool

from app.config import get_settings


def normalizar_url(url: str) -> str:
    """Aceita `postgres://` e `postgresql://` e força o driver psycopg 3."""
    if url.startswith("postgres://"):
        url = "postgresql://" + url.removeprefix("postgres://")
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url.removeprefix("postgresql://")
    return url


@lru_cache
def get_engine() -> Engine:
    settings = get_settings()
    url = normalizar_url(settings.database_url)
    if settings.db_serverless or os.environ.get("VERCEL"):
        # Cada invocação pode ser uma instância nova: a conexão fica com o pooler
        # (Supavisor/PgBouncer em modo transação), que não aceita prepared statements.
        return create_engine(url, poolclass=pool.NullPool, connect_args={"prepare_threshold": None})
    return create_engine(url, pool_pre_ping=True)
