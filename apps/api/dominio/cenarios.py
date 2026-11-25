"""Níveis de suporte e resistência e cenários condicionais (Fase 2, seção 3.3 da spec).

Os níveis vêm de pivôs nos candles semanais dos últimos 3 anos. Os cenários são
condicionais ("se o preço fechar acima de...") e sempre mostram o nível que os
invalida. Não há probabilidade (seção 1 da spec).
"""

import math
from dataclasses import asdict, dataclass, field
from datetime import date
from typing import Literal

import pandas as pd

from dominio import formato as f
from dominio.indicadores import atr

JANELA_PIVO = 2  # semanas de cada lado
MAX_NIVEIS = 3
ALVO_SEM_NIVEL_ATR = 2.0
INVALIDACAO_ATR = 1.5

TipoNivel = Literal["suporte", "resistencia", "max_52s", "min_52s"]


@dataclass(frozen=True)
class Nivel:
    preco: float
    tipo: TipoNivel
    toques: int


@dataclass(frozen=True)
class Cenario:
    tipo: Literal["alta", "lateral", "baixa"]
    titulo: str
    texto: str
    gatilho: float | None = None
    alvo: float | None = None
    invalidacao: float | None = None
    limite_inferior: float | None = None
    limite_superior: float | None = None
    dist_gatilho: float | None = None
    dist_alvo: float | None = None
    dist_invalidacao: float | None = None
    relacao: float | None = None  # distância gatilho→alvo sobre gatilho→invalidação


@dataclass(frozen=True)
class Analise:
    data: date
    preco: float
    atr14: float
    niveis: list[Nivel] = field(default_factory=list)
    cenarios: list[Cenario] = field(default_factory=list)

    def niveis_json(self) -> list[dict]:
        return [asdict(n) for n in self.niveis]

    def cenarios_json(self) -> list[dict]:
        return [asdict(c) for c in self.cenarios]


def pivos(semanal: pd.DataFrame, janela: int = JANELA_PIVO) -> list[float]:
    """Topos (máxima maior que as `janela` semanas de cada lado) e fundos (mínima menor)."""
    alta, baixa = semanal["maxima"].astype(float), semanal["minima"].astype(float)
    saida: list[float] = []
    for i in range(janela, len(semanal) - janela):
        vizinhos = list(range(i - janela, i)) + list(range(i + 1, i + janela + 1))
        if all(alta.iloc[i] > alta.iloc[j] for j in vizinhos):
            saida.append(float(alta.iloc[i]))
        if all(baixa.iloc[i] < baixa.iloc[j] for j in vizinhos):
            saida.append(float(baixa.iloc[i]))
    return saida


def agrupar(precos: list[float], distancia: float) -> list[tuple[float, int]]:
    """Junta pivôs a menos de `distancia` do grupo atual: (preço médio, toques)."""
    grupos: list[list[float]] = []
    for p in sorted(precos):
        if grupos and p - sum(grupos[-1]) / len(grupos[-1]) < distancia:
            grupos[-1].append(p)
        else:
            grupos.append([p])
    return [(sum(g) / len(g), len(g)) for g in grupos]


def _mais_fortes(grupos: list[tuple[float, int]], preco: float) -> list[tuple[float, int]]:
    escolhidos = sorted(grupos, key=lambda g: (-g[1], abs(g[0] - preco)))[:MAX_NIVEIS]
    return sorted(escolhidos, key=lambda g: abs(g[0] - preco))


def calcular_niveis(
    semanal: pd.DataFrame, preco: float, max_52s: float | None, min_52s: float | None
) -> tuple[list[Nivel], float]:
    """Níveis ordenados do mais próximo ao mais distante, e o ATR(14) semanal."""
    atr_sem = atr(semanal["maxima"].astype(float), semanal["minima"].astype(float),
                  semanal["fechamento"].astype(float)).iloc[-1]  # fmt: skip
    atr_sem = float(atr_sem) if not math.isnan(atr_sem) else 0.0
    grupos = agrupar(pivos(semanal), atr_sem)
    suportes = _mais_fortes([g for g in grupos if g[0] < preco], preco)
    resistencias = _mais_fortes([g for g in grupos if g[0] > preco], preco)
    niveis = [Nivel(round(p, 4), "suporte", t) for p, t in suportes]
    niveis += [Nivel(round(p, 4), "resistencia", t) for p, t in resistencias]
    # Os extremos de 52 semanas só entram se não coincidirem com um nível já encontrado.
    for valor, tipo in ((max_52s, "max_52s"), (min_52s, "min_52s")):
        if valor is not None and all(abs(n.preco - valor) > valor * 0.0025 for n in niveis):
            niveis.append(Nivel(round(valor, 4), tipo, 1))
    return niveis, atr_sem


def _dist(alvo: float, preco: float) -> float:
    return round((alvo / preco - 1) * 100, 2)


def _sinal(v: float) -> str:
    return f"{'+' if v > 0 else '−' if v < 0 else ''}{f.pct(abs(v))}"


def montar_cenarios(niveis: list[Nivel], preco: float, atr_diario: float) -> list[Cenario]:
    # Máxima e mínima de 52 semanas também servem de referência quando não há pivô.
    acima = sorted({n.preco for n in niveis if n.preco > preco})
    abaixo = sorted({n.preco for n in niveis if n.preco < preco}, reverse=True)
    cenarios: list[Cenario] = []

    if acima:
        r1 = acima[0]
        alvo = acima[1] if len(acima) > 1 else r1 + ALVO_SEM_NIVEL_ATR * atr_diario
        inv = r1 - INVALIDACAO_ATR * atr_diario
        cenarios.append(
            Cenario(
                "alta", "Cenário de alta",
                f"Se o preço fechar acima de {f.brl(r1)} ({_sinal(_dist(r1, preco))}), a "
                f"próxima referência é {f.brl(alvo)} ({_sinal(_dist(alvo, preco))}). O cenário "
                f"perde validade com um fechamento abaixo de {f.brl(inv)}.",
                gatilho=r1, alvo=alvo, invalidacao=inv, dist_gatilho=_dist(r1, preco),
                dist_alvo=_dist(alvo, preco), dist_invalidacao=_dist(inv, preco),
                relacao=round((alvo - r1) / (r1 - inv), 2) if r1 > inv else None,
            )
        )  # fmt: skip
    if acima and abaixo:
        s1, r1 = abaixo[0], acima[0]
        cenarios.append(
            Cenario(
                "lateral", "Cenário lateral",
                f"Enquanto o preço fechar entre {f.brl(s1)} ({_sinal(_dist(s1, preco))}) e "
                f"{f.brl(r1)} ({_sinal(_dist(r1, preco))}), ele segue dentro da faixa atual, "
                "sem romper o suporte nem a resistência mais próximos.",
                limite_inferior=s1, limite_superior=r1,
                dist_gatilho=None, dist_alvo=None, dist_invalidacao=None,
            )
        )  # fmt: skip
    if abaixo:
        s1 = abaixo[0]
        alvo = abaixo[1] if len(abaixo) > 1 else max(s1 - ALVO_SEM_NIVEL_ATR * atr_diario, 0.01)
        inv = s1 + INVALIDACAO_ATR * atr_diario
        cenarios.append(
            Cenario(
                "baixa", "Cenário de baixa",
                f"Se o preço fechar abaixo de {f.brl(s1)} ({_sinal(_dist(s1, preco))}), a "
                f"próxima referência é {f.brl(alvo)} ({_sinal(_dist(alvo, preco))}). O cenário "
                f"perde validade com um fechamento acima de {f.brl(inv)}.",
                gatilho=s1, alvo=alvo, invalidacao=inv, dist_gatilho=_dist(s1, preco),
                dist_alvo=_dist(alvo, preco), dist_invalidacao=_dist(inv, preco),
                relacao=round((s1 - alvo) / (inv - s1), 2) if inv > s1 else None,
            )
        )  # fmt: skip
    return cenarios


def calcular_cenarios(
    semanal: pd.DataFrame,
    data: date,
    preco: float,
    atr_diario: float | None,
    max_52s: float | None,
    min_52s: float | None,
) -> Analise | None:
    """`semanal`: candles semanais (maxima, minima, fechamento) dos últimos 3 anos."""
    if atr_diario is None or math.isnan(atr_diario) or atr_diario <= 0 or len(semanal) < 30:
        return None
    niveis, _ = calcular_niveis(semanal, preco, max_52s, min_52s)
    return Analise(data, preco, atr_diario, niveis, montar_cenarios(niveis, preco, atr_diario))
