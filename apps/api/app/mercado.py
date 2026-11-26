"""Resumo dos indicadores de mercado (Ibovespa, IFIX, dólar...) para a landing e /mercado."""

from collections import defaultdict
from datetime import date, timedelta

from sqlalchemy import Connection, text

INDICADORES: list[tuple[str, str, str]] = [
    ("ibov", "Ibovespa", "pontos"),
    ("ifix", "IFIX", "pontos"),
    ("smll", "Small Caps", "pontos"),
    ("idiv", "Dividendos (IDIV)", "pontos"),
    ("dolar", "Dólar", "reais"),
    ("euro", "Euro", "reais"),
    ("sp500", "S&P 500", "pontos"),
    ("bitcoin", "Bitcoin", "dolares"),
]


def _var(atual: float, base: float | None) -> float | None:
    return (atual / base - 1) * 100 if base else None


def indicadores(conn: Connection, hoje: date) -> list[dict]:
    desde = date(hoje.year - 2, 12, 1)
    linhas = conn.execute(
        text(
            "SELECT serie, data, valor FROM indices WHERE serie = ANY(:s) AND data >= :d "
            "ORDER BY serie, data"
        ),
        {"s": [c for c, _, _ in INDICADORES], "d": desde},
    ).all()
    por_serie: dict[str, list[tuple[date, float]]] = defaultdict(list)
    for serie, d, v in linhas:
        por_serie[serie].append((d, float(v)))

    saida = []
    for codigo, nome, unidade in INDICADORES:
        pts = por_serie.get(codigo)
        if not pts:
            continue
        data, valor = pts[-1]
        anterior = pts[-2][1] if len(pts) > 1 else None
        fim_ano = next((v for d, v in reversed(pts) if d.year < data.year), None)
        ha_um_ano = next((v for d, v in reversed(pts) if d <= data - timedelta(days=365)), None)
        # Um ponto por semana (o último de cada semana) nos últimos 12 meses.
        semanas: dict[tuple[int, int], tuple[date, float]] = {}
        for d, v in pts:
            if d > data - timedelta(days=365):
                semanas[d.isocalendar()[:2]] = (d, v)
        saida.append(
            {
                "serie": codigo,
                "nome": nome,
                "unidade": unidade,
                "data": data,
                "valor": valor,
                "var_dia": _var(valor, anterior),
                "var_ano": _var(valor, fim_ano),
                "var_12m": _var(valor, ha_um_ano),
                "pontos": [{"data": d, "valor": v} for d, v in sorted(semanas.values())],
            }
        )
    return saida
