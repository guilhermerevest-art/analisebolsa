"""Carga do histórico completo.

Uso: `python -m worker.backfill [--tickers PETR4,VALE3] [--desde 2005-01-01]`.

Pode ser interrompido e retomado: ativos que já têm histórico são pulados.
"""

import argparse
import logging
import sys
from collections.abc import Sequence
from datetime import date

from sqlalchemy import Engine

from app.config import Settings, get_settings
from app.db import get_engine
from fontes.cadeia import CadeiaFontes, criar_cadeia
from worker import repositorio as repo
from worker.analise import atualizar_analise
from worker.eod import hoje_b3
from worker.processamento import INICIO_HISTORICO, processar_ativos, sincronizar_catalogo

log = logging.getLogger("worker.backfill")


def executar_backfill(
    engine: Engine,
    fontes: CadeiaFontes,
    settings: Settings,
    hoje: date,
    *,
    tickers: Sequence[str] | None = None,
    desde: date = INICIO_HISTORICO,
    dormir=None,
) -> str:
    with engine.begin() as conn:
        vazio = repo.contar_ativos(conn) == 0
    if vazio:
        sincronizar_catalogo(engine, fontes)

    with engine.begin() as conn:
        execucao = repo.iniciar_execucao(conn, "backfill")
        candidatos = repo.listar_ativos_ativos(conn, tickers)
        pendentes = [(a, t) for a, t in candidatos if repo.primeira_data(conn, a) is None]
    log.info("backfill: %d pendentes de %d", len(pendentes), len(candidatos))
    res = processar_ativos(
        engine,
        fontes,
        pendentes,
        hoje,
        desde=desde,
        pausa_s=settings.pausa_entre_tickers_s,
        dormir=dormir,
    )
    res.detalhes["analise"] = atualizar_analise(engine, pendentes)
    res.detalhes["pulados"] = len(candidatos) - len(pendentes)
    res.detalhes["desde"] = desde.isoformat()
    with engine.begin() as conn:
        repo.finalizar_execucao(conn, execucao, res.status, res.ok, res.erro, res.detalhes)
    log.info("backfill %s: %d ok, %d com erro", res.status, res.ok, res.erro)
    return res.status


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Backfill do histórico do analisebolsa")
    parser.add_argument("--tickers", help="lista separada por vírgula (padrão: todos)")
    parser.add_argument("--desde", type=date.fromisoformat, default=INICIO_HISTORICO)
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    settings = get_settings()
    tickers = [t.strip().upper() for t in args.tickers.split(",")] if args.tickers else None
    status = executar_backfill(
        get_engine(), criar_cadeia(settings), settings, hoje_b3(), tickers=tickers, desde=args.desde
    )
    return 1 if status == "erro" else 0


if __name__ == "__main__":
    sys.exit(main())
