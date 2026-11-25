"""Recalcula a análise (métricas, insights e cenários) sem buscar dados.

Uso: `python -m worker.analise [--tickers PETR4,VALE3]`. O EOD chama
`atualizar_analise` para os ativos com pregão novo; depois do backfill ou de uma
mudança de regra, rode este comando para todos.
"""

import argparse
import logging
import sys
from collections.abc import Iterable, Sequence

from sqlalchemy import Engine

from app.db import get_engine
from dominio.cenarios import calcular_cenarios
from dominio.insights import Contexto, elegibilidade, gerar_insights
from dominio.metricas import JANELA_DIAS, calcular_metricas
from worker import repositorio as repo
from worker.processamento import status_por_contagem

log = logging.getLogger("worker.analise")


def analisar_ativo(engine: Engine, ativo_id: int) -> bool:
    """Grava métricas, insights e cenários de um ativo. Devolve False se ele não tem cotações."""
    with engine.begin() as conn:
        cot, ind, total = repo.carregar_para_analise(conn, ativo_id, JANELA_DIAS)
        if cot.empty:
            return False
        metricas = calcular_metricas(cot, ind, repo.ultimos_fundamentos(conn, ativo_id), total)
        if metricas is None:
            return False
        repo.upsert_metricas(conn, ativo_id, metricas.como_dict())
        setor = repo.setor_do_ativo(conn, ativo_id)
        contexto = Contexto(
            cotacoes=cot,
            indicadores=ind,
            metricas=metricas,
            setor=setor,
            dy_anos=repo.dy_anos_anteriores(conn, ativo_id, metricas.data.year),
            pl_pares=repo.pl_do_setor(conn, ativo_id, setor),
        )
        repo.substituir_insights(conn, ativo_id, metricas.data, gerar_insights(contexto))
        cenarios = None
        if elegibilidade(metricas.pregoes, metricas.volume_financeiro_20d)[0]:
            cenarios = calcular_cenarios(
                repo.carregar_semanal(conn, ativo_id),
                metricas.data,
                float(metricas.preco),
                contexto.ultimo("atr14"),
                float(metricas.max_52s) if metricas.max_52s is not None else None,
                float(metricas.min_52s) if metricas.min_52s is not None else None,
            )
        repo.gravar_cenarios(conn, ativo_id, cenarios)
    return True


def atualizar_analise(engine: Engine, ativos: Iterable[tuple[int, str]]) -> str:
    ativos = list(ativos)
    if not ativos:
        return "ignorada"  # feriado ou nada novo: não polui o histórico do job
    with engine.begin() as conn:
        execucao = repo.iniciar_execucao(conn, "analise")
    ok = erro = sem_dados = 0
    erros: dict[str, str] = {}
    for ativo_id, ticker in ativos:
        try:
            if analisar_ativo(engine, ativo_id):
                ok += 1
            else:
                sem_dados += 1
        except Exception as e:
            log.exception("falha na análise de %s", ticker)
            erro += 1
            erros[ticker] = f"{type(e).__name__}: {e}"[:500]
    status = status_por_contagem(ok, erro)
    with engine.begin() as conn:
        repo.finalizar_execucao(
            conn, execucao, status, ok, erro, {"erros": erros, "sem_dados": sem_dados}
        )
    log.info("análise %s: %d ok, %d com erro, %d sem dados", status, ok, erro, sem_dados)
    return status


def executar(engine: Engine, tickers: Sequence[str] | None = None) -> str:
    with engine.begin() as conn:
        ativos = repo.listar_ativos_ativos(conn, tickers)
    return atualizar_analise(engine, ativos)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Recalcula a análise do analisebolsa")
    parser.add_argument("--tickers", help="lista separada por vírgula (padrão: todos)")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    tickers = [t.strip().upper() for t in args.tickers.split(",")] if args.tickers else None
    return 1 if executar(get_engine(), tickers) == "erro" else 0


if __name__ == "__main__":
    sys.exit(main())
