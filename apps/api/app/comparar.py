"""Comparação de até 4 ativos: desempenho na base 100 e métricas lado a lado."""

from collections import defaultdict
from datetime import date

from sqlalchemy import Connection, text

from app.erros import Problema
from app.screener import COLUNAS_SAIDA

MAXIMO = 4
PONTOS_MAXIMO = 800


def comparar(conn: Connection, tickers: list[str], inicio: date) -> dict:
    tickers = list(dict.fromkeys(t.strip().upper() for t in tickers if t.strip()))
    if not 2 <= len(tickers) <= MAXIMO:
        raise Problema(422, f"escolha de 2 a {MAXIMO} ativos")
    ativos = {
        r["ticker"]: dict(r)
        for r in conn.execute(
            text(
                f"SELECT {COLUNAS_SAIDA} FROM ativos a "
                "LEFT JOIN metricas_ativo m USING (ativo_id) WHERE a.ticker = ANY(:t)"
            ),
            {"t": tickers},
        ).mappings()
    }
    faltando = [t for t in tickers if t not in ativos]
    if faltando:
        raise Problema(404, f"ativo não encontrado: {', '.join(faltando)}")

    linhas = conn.execute(
        text(
            "SELECT a.ticker, c.data, c.fechamento_ajustado FROM cotacoes_diarias c "
            "JOIN ativos a USING (ativo_id) WHERE a.ticker = ANY(:t) AND c.data >= :i "
            "ORDER BY c.data"
        ),
        {"t": tickers, "i": inicio},
    ).all()
    precos: dict[str, list[tuple[date, float]]] = defaultdict(list)
    for t, d, v in linhas:
        precos[t].append((d, float(v)))

    # Base 100 a partir do primeiro dia em que todos têm cotação, para a corrida começar junta.
    inicios = [precos[t][0][0] for t in tickers if precos.get(t)]
    base_data = max(inicios) if len(inicios) == len(tickers) else None
    series = []
    for t in tickers:
        pts = [(d, v) for d, v in precos.get(t, []) if base_data and d >= base_data]
        base = pts[0][1] if pts else None
        valores = [(d, v / base * 100) for d, v in pts] if base else []
        if len(valores) > PONTOS_MAXIMO:  # o último de cada semana
            semanas: dict[tuple[int, int], tuple[date, float]] = {}
            for d, v in valores:
                semanas[d.isocalendar()[:2]] = (d, v)
            valores = sorted(semanas.values())
        series.append(
            {"ticker": t, "pontos": [{"data": d, "valor": round(v, 4)} for d, v in valores]}
        )
    return {
        "inicio": base_data,
        "ativos": [ativos[t] for t in tickers],
        "series": series,
    }
