"""Índices da B3 (IFIX, Small Caps, Dividendos...) pelas estatísticas públicas do site da B3.

A consulta devolve um ano por vez: uma linha por dia do mês (1 a 31) e uma coluna por mês
("rateValue1" a "rateValue12"), com o fechamento no formato brasileiro ("3.311,48").
"""

import base64
import json
from datetime import date

from fontes.base import ClienteHttp, ErroFonte

URL = "https://sistemaswebb3-listados.b3.com.br/indexStatisticsProxy/IndexCall/GetPortfolioDay/{q}"


def _numero(v: str | None) -> float | None:
    if not v:
        return None
    try:
        return float(v.replace(".", "").replace(",", "."))
    except ValueError:
        return None


def parse_ano(dados: dict, ano: int) -> list[tuple[date, float]]:
    if not isinstance(dados, dict) or "results" not in dados:
        raise ErroFonte(f"b3: resposta inesperada: {str(dados)[:200]}")
    if dados["results"] is None:  # ano antes de o índice existir
        return []
    saida = []
    for linha in dados["results"]:
        dia = linha.get("day")
        for mes in range(1, 13):
            valor = _numero(linha.get(f"rateValue{mes}"))
            if valor is None or not dia:
                continue
            try:
                saida.append((date(ano, mes, int(dia)), valor))
            except ValueError:  # 30 de fevereiro etc.
                continue
    return sorted(saida)


class B3IndicesFonte:
    nome = "b3"

    def __init__(self, http: ClienteHttp | None = None) -> None:
        self.http = http or ClienteHttp()

    def serie(self, indice: str, inicio: date, fim: date) -> list[tuple[date, float]]:
        saida: list[tuple[date, float]] = []
        for ano in range(inicio.year, fim.year + 1):
            consulta = json.dumps({"index": indice, "language": "pt-br", "year": str(ano)})
            q = base64.b64encode(consulta.encode()).decode()
            status, dados = self.http.get_json(URL.format(q=q))
            if status == 404:
                continue
            saida += [(d, v) for d, v in parse_ano(dados, ano) if inicio <= d <= fim]
        return saida
