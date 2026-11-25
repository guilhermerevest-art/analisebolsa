"""Simulador de aportes: histórico mês a mês e faixa de resultados simulados (puro, sem I/O).

Histórico: o aporte mensal entra no primeiro pregão de cada mês (o inicial junto, no
primeiro), comprado ao fechamento. A quantidade é contada em unidades ajustadas, porque os
fechamentos do banco já vêm ajustados por eventos societários; o provento por ação da época
vira provento por unidade ajustada dividindo pelo fator dos eventos com data-com igual ou
posterior. O provento vale para a custódia no fim da data-com, entra no patrimônio como
valor a receber e cai no caixa no primeiro pregão a partir do pagamento, quando é
reinvestido (se a opção estiver ligada). Os mesmos aportes rendem o CDI de cada dia útil e
são corrigidos pelo IPCA de cada mês, na virada para o mês seguinte.

Faixa simulada: bootstrap circular em blocos de 12 meses dos retornos mensais totais do
ativo (proventos reinvestidos), com os mesmos aportes e o mesmo número de meses do período.
"""

import hashlib
from bisect import bisect_left
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from itertools import pairwise

import numpy as np

from dominio.modelos import Provento
from dominio.rentabilidade import fator_ate_eventos

TRAJETORIAS = 2000
BLOCO_MESES = 12
MESES_MINIMOS = 60

AVISO = (
    "Simulação com dados históricos, sem impostos nem custos de corretagem. Rentabilidade "
    "passada não garante resultado futuro."
)
EXPLICACAO_FAIXA = (
    f"Os retornos mensais do ativo, com proventos reinvestidos, foram separados em blocos de "
    f"{BLOCO_MESES} meses e sorteados em sequência para montar {TRAJETORIAS:_} trajetórias "
    "com os mesmos aportes e a mesma duração do período escolhido. A faixa vai do percentil 10 "
    "ao 90 do patrimônio dessas trajetórias em cada mês, e a linha do meio é a mediana. É um "
    "exercício sobre o histórico, não uma previsão: o resultado real pode ficar fora da faixa."
).replace("_", ".")


@dataclass(frozen=True, slots=True)
class PontoSimulacao:
    data: date  # último dia do mês com dado (ou o último do período)
    aportado: float
    patrimonio: float | None  # None quando não há ativo
    proventos: float | None  # acumulado no período
    cdi: float | None
    ipca: float | None


@dataclass(frozen=True, slots=True)
class PontoFaixa:
    data: date
    p10: float
    p50: float
    p90: float


@dataclass(frozen=True, slots=True)
class Faixa:
    meses_historico: int
    pontos: list[PontoFaixa]


def _mes(d: date) -> tuple[int, int]:
    return d.year, d.month


def aportes_do_calendario(
    calendario: list[date], aporte_inicial: float, aporte_mensal: float
) -> dict[date, float]:
    """O primeiro dia de cada mês recebe o aporte mensal; o primeiro de todos, também o inicial."""
    saida: dict[date, float] = {}
    mes_anterior = None
    for d in calendario:
        if _mes(d) != mes_anterior:
            saida[d] = aporte_mensal + (aporte_inicial if mes_anterior is None else 0.0)
            mes_anterior = _mes(d)
    return saida


def simular(
    inicio: date,
    aporte_inicial: float,
    aporte_mensal: float,
    *,
    precos: dict[date, Decimal] | None = None,
    proventos: Iterable[Provento] = (),
    cdi: dict[date, float] | None = None,
    ipca: dict[date, float] | None = None,
    reinvestir: bool = True,
) -> list[PontoSimulacao]:
    """Pontos mensais do período, do primeiro dia com dado a partir de `inicio` até o último.

    Com `precos`, o calendário são os pregões do ativo; sem ativo, os dias do CDI.
    """
    cdi, ipca = cdi or {}, ipca or {}
    base = precos if precos is not None else cdi
    calendario = sorted(d for d in base if d >= inicio)
    if not calendario:
        return []
    aportes = aportes_do_calendario(calendario, aporte_inicial, aporte_mensal)

    # Ativo
    lista = sorted(proventos, key=lambda p: p.data_com)
    fator = fator_ate_eventos([p for p in lista if p.societario and p.valor > 0])
    caixa_por_data_com: dict[date, list[Provento]] = defaultdict(list)
    for p in lista:
        if not p.societario and p.valor > 0 and p.data_com >= calendario[0]:
            caixa_por_data_com[p.data_com].append(p)
    datas_com = sorted(caixa_por_data_com)
    i_com = 0
    quantidade = caixa = 0.0
    a_receber: list[tuple[date, float]] = []  # (pagamento, valor)
    total_proventos = 0.0

    # CDI: rende em todo dia útil depois do primeiro dia; IPCA: na virada de cada mês.
    dias_cdi = sorted(x for x in cdi if x > calendario[0])
    i_cdi = 0
    saldo_cdi = saldo_ipca = aportado = 0.0
    mes_corrente = _mes(calendario[0])

    pontos: list[PontoSimulacao] = []
    for n, d in enumerate(calendario):
        while i_cdi < len(dias_cdi) and dias_cdi[i_cdi] <= d:
            saldo_cdi *= 1 + cdi[dias_cdi[i_cdi]] / 100
            i_cdi += 1
        if _mes(d) != mes_corrente:
            # Corrige pelo IPCA de cada mês que terminou (pode haver mês sem dia no calendário).
            a, m = mes_corrente
            while (a, m) < _mes(d):
                saldo_ipca *= 1 + ipca.get(date(a, m, 1), 0.0) / 100
                a, m = (a + 1, 1) if m == 12 else (a, m + 1)
            mes_corrente = _mes(d)

        valor_aporte = aportes.get(d, 0.0)
        aportado += valor_aporte
        saldo_cdi += valor_aporte
        saldo_ipca += valor_aporte

        patrimonio = None
        if precos is not None:
            preco = float(precos[d])
            # Proventos com pagamento até hoje caem no caixa.
            pagos = [v for pg, v in a_receber if pg <= d]
            a_receber = [(pg, v) for pg, v in a_receber if pg > d]
            caixa += sum(pagos) + valor_aporte
            if reinvestir or valor_aporte:
                investir = caixa if reinvestir else valor_aporte
                quantidade += investir / preco
                caixa -= investir
            # Fim do dia: proventos com data-com até hoje valem para a custódia.
            while i_com < len(datas_com) and datas_com[i_com] <= d:
                dc = datas_com[i_com]
                f = float(fator(dc))
                for p in caixa_por_data_com[dc]:
                    valor = quantidade * float(p.valor) / f
                    pagamento = p.data_pagamento or dc + timedelta(days=1)
                    a_receber.append((max(pagamento, dc + timedelta(days=1)), valor))
                    total_proventos += valor
                i_com += 1
            patrimonio = quantidade * preco + caixa + sum(v for _, v in a_receber)

        ultimo_do_mes = n + 1 == len(calendario) or _mes(calendario[n + 1]) != _mes(d)
        if ultimo_do_mes:
            pontos.append(
                PontoSimulacao(
                    d,
                    round(aportado, 2),
                    round(patrimonio, 2) if patrimonio is not None else None,
                    round(total_proventos, 2) if precos is not None else None,
                    round(saldo_cdi, 2) if cdi else None,
                    round(saldo_ipca, 2) if ipca else None,
                )
            )
    return pontos


def retornos_mensais(precos: dict[date, Decimal], proventos: Iterable[Provento]) -> list[float]:
    """Retornos mensais totais: preço ajustado mais proventos reinvestidos na data ex.

    O primeiro mês (provavelmente parcial) fica de fora.
    """
    datas = sorted(precos)
    if len(datas) < 2:
        return []
    lista = sorted(proventos, key=lambda p: p.data_com)
    fator = fator_ate_eventos([p for p in lista if p.societario and p.valor > 0])
    por_ajuste: dict[date, float] = defaultdict(float)  # data ex -> provento por unidade ajustada
    for p in lista:
        if p.societario or p.valor <= 0:
            continue
        i = bisect_left(datas, p.data_com + timedelta(days=1))
        if i < len(datas):
            por_ajuste[datas[i]] += float(p.valor) / float(fator(p.data_com))

    indice = 1.0
    fim_do_mes: list[float] = []
    for i, d in enumerate(datas):
        if i:
            anterior = float(precos[datas[i - 1]])
            indice *= (float(precos[d]) + por_ajuste.get(d, 0.0)) / anterior
        if i + 1 == len(datas) or _mes(datas[i + 1]) != _mes(d):
            fim_do_mes.append(indice)
    return [b / a - 1 for a, b in pairwise(fim_do_mes)]


def semente(*partes: object) -> int:
    texto = "|".join(str(p) for p in partes)
    return int.from_bytes(hashlib.sha256(texto.encode()).digest()[:8], "big")


def faixa_simulada(
    retornos: list[float],
    datas: list[date],
    aporte_inicial: float,
    aporte_mensal: float,
    semente_: int,
    trajetorias: int = TRAJETORIAS,
) -> Faixa | None:
    """Percentis 10, 50 e 90 do patrimônio em cada mês de `datas` (um ponto por mês)."""
    n, meses = len(retornos), len(datas)
    if n < MESES_MINIMOS or meses < 2:
        return None
    gerador = np.random.default_rng(semente_)
    blocos = -(-meses // BLOCO_MESES)
    inicios = gerador.integers(0, n, size=(trajetorias, blocos))
    indices = (inicios[:, :, None] + np.arange(BLOCO_MESES)) % n
    r = np.asarray(retornos)[indices.reshape(trajetorias, -1)[:, :meses]]

    valor = np.zeros(trajetorias)
    percentis = np.empty((meses, 3))
    for m in range(meses):
        valor = (valor + aporte_mensal + (aporte_inicial if m == 0 else 0.0)) * (1 + r[:, m])
        percentis[m] = np.percentile(valor, [10, 50, 90])
    return Faixa(
        n,
        [
            PontoFaixa(d, round(float(a), 2), round(float(b), 2), round(float(c), 2))
            for d, (a, b, c) in zip(datas, percentis, strict=True)
        ],
    )
