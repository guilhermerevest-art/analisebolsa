"""Conexão com o Postgres (SQLAlchemy 2 core + psycopg 3)."""

from functools import lru_cache

from sqlalchemy import Engine, create_engine

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
    return create_engine(normalizar_url(get_settings().database_url), pool_pre_ping=True)
