"""Backtest: carrega o histórico ajustado e o CDI e chama o domínio."""

from datetime import date, timedelta

import pandas as pd
from sqlalchemy import Connection, text

from app import consultas as q
from app.carteira import _indice
from app.erros import Problema
from dominio import backtest as bt

# Dias corridos antes do início para aquecer a maior janela (250 pregões).
AQUECIMENTO_DIAS = 400


def _historico(conn: Connection, ativo_id: int, inicio: date, fim: date) -> pd.DataFrame:
    linhas = conn.execute(
        text(
            """
            SELECT data, abertura, maxima, minima, fechamento, fechamento_ajustado
            FROM cotacoes_diarias
            WHERE ativo_id = :a AND data BETWEEN :i AND :f
            ORDER BY data
            """
        ),
        {"a": ativo_id, "i": inicio - timedelta(days=AQUECIMENTO_DIAS), "f": fim},
    ).all()
    colunas = ["abertura", "maxima", "minima", "fechamento", "fechamento_ajustado"]
    df = pd.DataFrame(
        [[float(v) for v in linha[1:]] for linha in linhas],
        index=[linha[0] for linha in linhas],
        columns=colunas,
    )
    return bt.ajustar(df)


def rodar(conn: Connection, ticker: str, inicio: date, fim: date, config: bt.Config) -> dict:
    ativo = q.ativo_por_ticker(conn, ticker)  # 404 se não existir
    try:
        parametros = bt.validar(config.estrategia, config.parametros)
    except bt.ParametrosInvalidos as e:
        raise Problema(422, str(e)) from e
    df = _historico(conn, ativo["ativo_id"], inicio, fim)
    cdi = _indice(conn, "cdi", inicio - timedelta(days=AQUECIMENTO_DIAS))
    r = bt.rodar(df, inicio, fim, cdi, config) if len(df) else None
    if r is None:
        raise Problema(
            422,
            f"{ticker} não tem pregões suficientes nesse período: o teste precisa de pelo "
            f"menos {bt.PREGOES_MINIMOS} depois do aquecimento dos indicadores",
        )
    e = bt.ESTRATEGIAS[config.estrategia]
    return {
        "ticker": ticker,
        "estrategia": config.estrategia,
        "nome": e.nome,
        "regra": r.regra,
        "parametros": parametros,
        "stop_atr": config.stop_atr,
        "capital": config.capital,
        "custos": {
            "corretagem": config.custos.corretagem,
            "taxas": config.custos.taxas,
            "deslizamento": config.custos.deslizamento,
            "total": r.custos,
        },
        "cdi_no_caixa": config.cdi_no_caixa,
        "inicio": r.inicio,
        "fim": r.fim,
        "divisao": r.divisao,
        "pontos": r.pontos,
        "total": r.total,
        "dentro_amostra": r.dentro,
        "fora_amostra": r.fora,
        "operacoes": r.operacoes,
        "aviso": bt.AVISO,
    }
