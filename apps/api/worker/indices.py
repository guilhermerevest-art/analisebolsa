"""Atualiza as séries de mercado: `python -m worker.indices`.

CDI, IPCA, dólar e euro (Banco Central); Ibovespa, S&P 500 e bitcoin (Yahoo); IFIX, Small Caps
e Dividendos (B3).

Roda no fim do EOD e no backfill. Cada série continua de onde parou; a falha de uma série
não impede as outras nem derruba o job que chamou.
"""

import logging
import sys
from collections.abc import Callable
from datetime import date, timedelta

from sqlalchemy import Engine, text

from app.config import get_settings
from app.db import get_engine
from fontes.b3 import B3IndicesFonte
from fontes.base import ClienteHttp
from fontes.bcb import BcbFonte
from fontes.yahoo import YahooFonte
from worker.processamento import INICIO_HISTORICO

log = logging.getLogger("worker.indices")
SERIES = ("cdi", "ipca", "ibov", "dolar", "euro", "ifix", "smll", "idiv", "sp500", "bitcoin")


def ultima_data(conn, serie: str) -> date | None:
    return conn.execute(
        text("SELECT max(data) FROM indices WHERE serie = :s"), {"s": serie}
    ).scalar_one()


def gravar(conn, serie: str, pontos: list[tuple[date, float]]) -> int:
    if not pontos:
        return 0
    conn.execute(
        text(
            "INSERT INTO indices (serie, data, valor) VALUES (:serie, :data, :valor) "
            "ON CONFLICT (serie, data) DO UPDATE SET valor = EXCLUDED.valor"
        ),
        [{"serie": serie, "data": d, "valor": v} for d, v in pontos],
    )
    return len(pontos)


def buscadores(http: ClienteHttp | None = None) -> dict[str, Callable]:
    bcb, yahoo, b3 = BcbFonte(http), YahooFonte(http), B3IndicesFonte(http)
    return {
        "cdi": lambda i, f: bcb.serie("cdi", i, f),
        "ipca": lambda i, f: bcb.serie("ipca", i, f),
        "ibov": lambda i, f: yahoo.indice("^BVSP", i, f),
        "dolar": lambda i, f: bcb.serie("dolar", i, f),
        "euro": lambda i, f: bcb.serie("euro", i, f),
        "ifix": lambda i, f: b3.serie("IFIX", i, f),
        "smll": lambda i, f: b3.serie("SMLL", i, f),
        "idiv": lambda i, f: b3.serie("IDIV", i, f),
        "sp500": lambda i, f: yahoo.indice("^GSPC", i, f),
        "bitcoin": lambda i, f: yahoo.indice("BTC-USD", i, f),
    }


def atualizar_indices(
    engine: Engine,
    hoje: date,
    *,
    desde: date = INICIO_HISTORICO,
    fontes: dict[str, Callable] | None = None,
) -> dict:
    """Devolve, por série, quantos pontos foram gravados ou a mensagem de erro."""
    fontes = fontes or buscadores()
    resultado: dict[str, int | str] = {}
    for serie in SERIES:
        try:
            with engine.begin() as conn:
                ultima = ultima_data(conn, serie)
            # O IPCA sai com data do primeiro dia do mês; o BCB revisa o último ponto às vezes.
            inicio = (
                desde if ultima is None else ultima - timedelta(days=40 if serie == "ipca" else 5)
            )
            if serie not in fontes:
                continue
            pontos = fontes[serie](inicio, hoje)
            with engine.begin() as conn:
                resultado[serie] = gravar(conn, serie, pontos)
        except Exception as e:  # uma série com problema não derruba as outras
            log.warning("índice %s falhou: %s", serie, e)
            resultado[serie] = f"erro: {e}"[:200]
    return resultado


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    from worker.eod import hoje_b3

    get_settings()
    res = atualizar_indices(get_engine(), hoje_b3())
    log.info("índices: %s", res)
    return 1 if all(isinstance(v, str) for v in res.values()) else 0


if __name__ == "__main__":
    sys.exit(main())
