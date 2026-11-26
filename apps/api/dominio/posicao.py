"""Calculadora de risco e tamanho de posição (puro, sem I/O).

A quantidade é a maior que mantém a perda até o stop dentro do risco escolhido (em % do
capital), arredondada para baixo no lote, e que não passa do limite de concentração.
"""

from dataclasses import dataclass
from math import floor


class PosicaoInvalida(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class Posicao:
    quantidade: int
    valor: float
    pct_capital: float  # fração
    distancia_stop: float  # fração do preço de entrada
    perda_stop: float  # R$
    perda_pct_capital: float  # fração
    risco_maximo: float  # R$ que o risco escolhido permitia
    limitada_por: str | None  # "concentracao", "capital" ou None
    alvos: list[tuple[int, float]]  # (múltiplo de R, preço)


def calcular(
    capital: float,
    risco_pct: float,
    entrada: float,
    stop: float,
    lote: int = 100,
    concentracao_pct: float = 25.0,
) -> Posicao:
    if stop >= entrada:
        raise PosicaoInvalida("o stop precisa ficar abaixo do preço de entrada")
    if stop <= 0:
        raise PosicaoInvalida("o stop precisa ser maior que zero")
    distancia = entrada - stop
    risco_maximo = capital * risco_pct / 100

    def no_lote(q: float) -> int:
        return floor(q / lote + 1e-9) * lote

    por_risco = no_lote(risco_maximo / distancia)
    por_concentracao = no_lote(capital * concentracao_pct / 100 / entrada)
    por_capital = no_lote(capital / entrada)
    quantidade = min(por_risco, por_concentracao, por_capital)
    limitada_por = None
    if quantidade < por_risco:
        limitada_por = "capital" if por_capital <= por_concentracao else "concentracao"
    valor = quantidade * entrada
    perda = quantidade * distancia
    return Posicao(
        quantidade,
        round(valor, 2),
        valor / capital,
        distancia / entrada,
        round(perda, 2),
        perda / capital,
        round(risco_maximo, 2),
        limitada_por,
        [(r, round(entrada + r * distancia, 2)) for r in (1, 2, 3)],
    )


def stop_por_atr(entrada: float, atr: float, multiplo: float) -> float:
    return round(entrada - multiplo * atr, 2)
