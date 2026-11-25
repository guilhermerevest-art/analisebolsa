"""Rentabilidade da carteira pelo retorno ponderado pelo tempo (TWR), contra CDI e Ibovespa.

Puro, sem I/O. Os fluxos do dia (compras, vendas e proventos) são tratados como feitos no
fechamento, então o retorno do dia é (valor + saídas − entradas) / valor do dia anterior. No
primeiro dia, ou quando a carteira estava zerada, o retorno vai do valor investido até o
fechamento. O acumulado encadeia os retornos diários, o que neutraliza aportes e retiradas.

Os fechamentos do banco são ajustados por eventos societários (o Yahoo entrega assim e a
brapi é ajustada em `dominio.ajuste`). Para valorizar a quantidade realmente em carteira,
o preço do dia volta ao valor da época multiplicando pelos fatores dos eventos com data-com
igual ou posterior ao dia.
"""

from bisect import bisect_left
from collections import defaultdict
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from dominio.carteira import Operacao, VendaAcimaDaPosicao
from dominio.modelos import Provento


@dataclass(frozen=True, slots=True)
class PontoRentabilidade:
    data: date
    patrimonio: float
    carteira: float  # acumulado em %
    cdi: float | None
    ibov: float | None


def fator_ate_eventos(eventos: list[Provento]) -> Callable[[date], Decimal]:
    """f(d) = produto dos fatores dos eventos com data-com >= d."""
    datas = [e.data_com for e in eventos]
    sufixo = [Decimal(1)] * (len(eventos) + 1)
    for i in range(len(eventos) - 1, -1, -1):
        sufixo[i] = sufixo[i + 1] * eventos[i].valor

    def fator(d: date) -> Decimal:
        return sufixo[bisect_left(datas, d)]

    return fator


def serie_rentabilidade(
    operacoes: Iterable[Operacao],
    proventos: dict[str, list[Provento]],
    precos: dict[str, dict[date, Decimal]],
    cdi: dict[date, float] | None = None,
    ibov: dict[date, float] | None = None,
) -> list[PontoRentabilidade]:
    ops = sorted(operacoes, key=lambda o: (o.data, o.id))
    if not ops:
        return []
    inicio = ops[0].data
    cdi, ibov = cdi or {}, ibov or {}

    ops_dia: dict[date, list[Operacao]] = defaultdict(list)
    for o in ops:
        ops_dia[o.data].append(o)
    caixa_dia: dict[date, list[Provento]] = defaultdict(list)
    eventos_dia: dict[date, list[Provento]] = defaultdict(list)
    fator: dict[str, Callable[[date], Decimal]] = {}
    for ticker in {o.ticker for o in ops}:
        lista = sorted(proventos.get(ticker, []), key=lambda p: p.data_com)
        societarios = [p for p in lista if p.societario and p.valor > 0]
        fator[ticker] = fator_ate_eventos(societarios)
        for p in lista:
            if p.data_com < inicio or p.valor <= 0:
                continue
            (eventos_dia if p.societario else caixa_dia)[p.data_com].append((ticker, p))

    datas = sorted({d for serie in precos.values() for d in serie if d >= inicio} | set(ops_dia))
    quantidade: dict[str, Decimal] = defaultdict(Decimal)
    ultimo_preco: dict[str, Decimal] = {}
    valor_anterior = 0.0
    a_receber = 0.0
    acumulado = 1.0
    cdi_acumulado = 1.0
    # O CDI rende em todo dia útil depois do início, mesmo que falte cotação no dia.
    dias_cdi = sorted(x for x in cdi if x > inicio)
    i_cdi = 0
    ibov_base = None
    ibov_ultimo = None
    saida: list[PontoRentabilidade] = []

    for d in datas:
        aportes = retiradas = 0.0
        for o in ops_dia.get(d, []):
            total = float(o.preco * o.quantidade)
            if o.tipo == "compra":
                quantidade[o.ticker] += o.quantidade
                aportes += total + float(o.custos)
                ultimo_preco.setdefault(o.ticker, o.preco / fator[o.ticker](d))
            else:
                if o.quantidade > quantidade[o.ticker]:
                    raise VendaAcimaDaPosicao(o.ticker, d, quantidade[o.ticker], o.quantidade)
                quantidade[o.ticker] -= o.quantidade
                retiradas += total - float(o.custos)

        valor = 0.0
        for ticker, q in quantidade.items():
            if ticker in precos and d in precos[ticker]:
                ultimo_preco[ticker] = precos[ticker][d]
            if q > 0 and ticker in ultimo_preco:
                valor += float(q * ultimo_preco[ticker] * fator[ticker](d))

        # O provento vale para a custódia no fim da data-com, mas o preço só cai no pregão
        # seguinte (data ex): ele entra como saída de caixa nesse pregão.
        retiradas += a_receber
        a_receber = sum((float(quantidade[t] * p.valor) for t, p in caixa_dia.get(d, [])), 0.0)
        for ticker, p in eventos_dia.get(d, []):
            quantidade[ticker] *= p.valor

        if valor_anterior > 0:
            acumulado *= (valor + retiradas - aportes) / valor_anterior
        elif aportes > 0:  # primeiro dia (ou recomeço): da compra ao fechamento
            acumulado *= (valor + retiradas) / aportes
        valor_anterior = valor

        while i_cdi < len(dias_cdi) and dias_cdi[i_cdi] <= d:
            cdi_acumulado *= 1 + cdi[dias_cdi[i_cdi]] / 100
            i_cdi += 1
        if d in ibov:
            ibov_ultimo = ibov[d]
            ibov_base = ibov_base or ibov_ultimo
        saida.append(
            PontoRentabilidade(
                d,
                round(valor, 2),
                (acumulado - 1) * 100,
                (cdi_acumulado - 1) * 100 if cdi else None,
                (ibov_ultimo / ibov_base - 1) * 100 if ibov_base else None,
            )
        )
    return saida


def reduzir(pontos: list[PontoRentabilidade], maximo: int = 800) -> list[PontoRentabilidade]:
    """Para séries longas, mantém o último ponto de cada semana (e sempre o último)."""
    if len(pontos) <= maximo:
        return pontos
    saida = []
    for i, p in enumerate(pontos):
        proxima = pontos[i + 1].data.isocalendar()[:2] if i + 1 < len(pontos) else None
        if p.data.isocalendar()[:2] != proxima:
            saida.append(p)
    return saida
