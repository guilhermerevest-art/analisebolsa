import os
from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, text

from app.db import normalizar_url
from dominio.modelos import Candle

TABELAS = (
    "cotacoes_diarias, indicadores_diarios, proventos, fundamentos, execucoes_job, ativos, "
    "indices, accounts, sessions, verification_tokens, users"
)


@pytest.fixture(scope="session")
def engine():
    url = os.environ.get("DATABASE_URL_TEST")
    if not url:
        pytest.skip("DATABASE_URL_TEST não definida")
    from alembic import command
    from alembic.config import Config

    cfg = Config(os.path.join(os.path.dirname(__file__), "..", "alembic.ini"))
    cfg.set_main_option(
        "script_location", os.path.join(os.path.dirname(__file__), "..", "migrations")
    )
    cfg.set_main_option("sqlalchemy.url", normalizar_url(url))
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
    eng = create_engine(normalizar_url(url))
    yield eng
    eng.dispose()


@pytest.fixture
def db(engine):
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {TABELAS} RESTART IDENTITY CASCADE"))
    return engine


def dias_uteis(inicio: date, fim: date) -> list[date]:
    dias, d = [], inicio
    while d <= fim:
        if d.weekday() < 5:
            dias.append(d)
        d += timedelta(days=1)
    return dias


def serie_candles(inicio: date, fim: date, base: float = 20.0) -> list[Candle]:
    """Série determinística com oscilação suave, sempre válida."""
    saida = []
    for i, d in enumerate(dias_uteis(inicio, fim)):
        preco = Decimal(str(round(base + (i % 17) * 0.13 - (i % 5) * 0.07, 2)))
        saida.append(
            Candle(d, preco, preco + Decimal("0.3"), preco - Decimal("0.3"), preco, preco, 1000 + i)
        )
    return saida
