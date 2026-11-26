"""Carteira: posição, preço médio, resultado realizado, eventos e proventos (puro, sem I/O).

Preço médio pelo método da Receita Federal: compras somam quantidade e custo (preço ×
quantidade + custos); vendas baixam a quantidade e o custo pelo preço médio, sem mudar o
preço médio. Num dia com compra e venda do mesmo ativo, a quantidade casada (a menor das
duas) é day trade: o resultado sai do preço médio das compras e das vendas do próprio dia, e
a posição não muda; só o que sobra entra como compra ou venda comum.

Desdobramento, grupamento e bonificação multiplicam a quantidade pelo fator no fim da
data-com e mantêm o custo total. Proventos em dinheiro valem para a quantidade
em custódia no fim da data-com.
"""

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from dominio.modelos import Provento

ZERO = Decimal(0)
CENTAVO = Decimal("0.01")
CASAS_QTD = Decimal("0.0001")


@dataclass(frozen=True, slots=True)
class Operacao:
    id: int
    ticker: str
    tipo: str  # 'compra' | 'venda'
    data: date
    quantidade: Decimal
    preco: Decimal
    custos: Decimal = ZERO


class VendaAcimaDaPosicao(ValueError):
    def __init__(self, ticker: str, data: date, disponivel: Decimal, pedida: Decimal):
        self.ticker, self.data, self.disponivel, self.pedida = ticker, data, disponivel, pedida
        super().__init__(
            f"venda de {_qtd(pedida)} {ticker} em {data:%d/%m/%Y}, "
            f"mas a posição nessa data era de {_qtd(disponivel)}"
        )


def _qtd(q: Decimal) -> str:
    return f"{q.normalize():f}".replace(".", ",")


@dataclass(frozen=True, slots=True)
class ProventoRecebido:
    ticker: str
    tipo: str
    data_com: date
    data_pagamento: date | None
    valor_unitario: Decimal
    quantidade: Decimal
    total: Decimal


@dataclass(slots=True)
class Posicao:
    ticker: str
    quantidade: Decimal = ZERO
    custo: Decimal = ZERO
    resultado_realizado: Decimal = ZERO
    proventos: Decimal = ZERO
    primeira_compra: date | None = None

    @property
    def preco_medio(self) -> Decimal | None:
        return (self.custo / self.quantidade) if self.quantidade > 0 else None


@dataclass(frozen=True, slots=True)
class VendaRealizada:
    """Uma venda com o custo baixado pelo preço médio (base da apuração do imposto)."""

    ticker: str
    data: date
    quantidade: Decimal
    valor: Decimal  # preço × quantidade, sem descontar custos
    custos: Decimal
    custo_medio: Decimal  # preço médio × quantidade vendida
    resultado: Decimal  # valor − custos − custo_medio
    day_trade: bool = False


@dataclass(slots=True)
class Consolidacao:
    posicoes: dict[str, Posicao] = field(default_factory=dict)
    proventos: list[ProventoRecebido] = field(default_factory=list)
    vendas: list[VendaRealizada] = field(default_factory=list)

    @property
    def abertas(self) -> list[Posicao]:
        return sorted(
            (p for p in self.posicoes.values() if p.quantidade > 0), key=lambda p: p.ticker
        )


def consolidar(
    operacoes: Iterable[Operacao],
    proventos: dict[str, list[Provento]] | None = None,
    ate: date | None = None,
) -> Consolidacao:
    """Processa operações e eventos em ordem cronológica, ativo por ativo.

    No mesmo dia, as operações vêm antes do fim da data-com (proventos e eventos). Levanta
    `VendaAcimaDaPosicao` se alguma venda passar da posição na data.
    """
    proventos = proventos or {}
    por_ticker: dict[str, list[Operacao]] = defaultdict(list)
    for op in operacoes:
        por_ticker[op.ticker].append(op)

    res = Consolidacao()
    for ticker, ops in sorted(por_ticker.items()):
        ops.sort(key=lambda o: (o.data, o.id))
        pos = Posicao(ticker)
        # (data, ordem, item): ordem 0 = operações do dia, 1 = provento em dinheiro, 2 = evento.
        dias: dict[date, list[Operacao]] = defaultdict(list)
        for o in ops:
            dias[o.data].append(o)
        linha: list[tuple[date, int, int, object]] = [
            (d, 0, lista[0].id, lista) for d, lista in dias.items()
        ]
        inicio = ops[0].data
        for i, p in enumerate(proventos.get(ticker, [])):
            if p.data_com < inicio or (ate and p.data_com > ate) or p.valor <= 0:
                continue
            linha.append((p.data_com, 2 if p.societario else 1, i, p))
        linha.sort(key=lambda x: x[:3])

        for _, ordem, _, item in linha:
            if ordem == 0:
                res.vendas.extend(_aplicar_dia(pos, item))
            elif ordem == 1 and pos.quantidade > 0:
                total = (pos.quantidade * item.valor).quantize(CENTAVO)
                pos.proventos += total
                res.proventos.append(
                    ProventoRecebido(
                        ticker,
                        item.tipo,
                        item.data_com,
                        item.data_pagamento,
                        item.valor,
                        pos.quantidade,
                        total,
                    )
                )
            elif ordem == 2 and pos.quantidade > 0:
                pos.quantidade = (pos.quantidade * item.valor).quantize(CASAS_QTD)
        res.posicoes[ticker] = pos
    res.proventos.sort(key=lambda p: (p.data_com, p.ticker))
    res.vendas.sort(key=lambda v: (v.data, v.ticker))
    return res


def _comprar(pos: Posicao, dia: date, quantidade: Decimal, custo: Decimal) -> None:
    pos.quantidade += quantidade
    pos.custo += custo
    pos.primeira_compra = pos.primeira_compra or dia


def _vender(
    pos: Posicao, dia: date, quantidade: Decimal, valor: Decimal, custos: Decimal
) -> VendaRealizada:
    if quantidade > pos.quantidade:
        raise VendaAcimaDaPosicao(pos.ticker, dia, pos.quantidade, quantidade)
    baixa = pos.custo / pos.quantidade * quantidade
    resultado = valor - custos - baixa
    pos.resultado_realizado += resultado
    pos.quantidade -= quantidade
    pos.custo = ZERO if pos.quantidade == 0 else pos.custo - baixa
    return VendaRealizada(pos.ticker, dia, quantidade, valor, custos, baixa, resultado)


def _aplicar_dia(pos: Posicao, ops: list[Operacao]) -> list[VendaRealizada]:
    """Operações de um ativo num dia, já em ordem de lançamento."""
    compras = [o for o in ops if o.tipo == "compra"]
    vendas = [o for o in ops if o.tipo == "venda"]
    dia = ops[0].data
    if not compras or not vendas:
        saida = []
        for o in ops:
            if o.tipo == "compra":
                _comprar(pos, dia, o.quantidade, o.preco * o.quantidade + o.custos)
            else:
                saida.append(_vender(pos, dia, o.quantidade, o.preco * o.quantidade, o.custos))
        return saida

    qc = sum((o.quantidade for o in compras), ZERO)
    qv = sum((o.quantidade for o in vendas), ZERO)
    custo_c = sum((o.preco * o.quantidade + o.custos for o in compras), ZERO)
    valor_v = sum((o.preco * o.quantidade for o in vendas), ZERO)
    custos_v = sum((o.custos for o in vendas), ZERO)
    casada = min(qc, qv)
    if qv - casada > pos.quantidade:
        raise VendaAcimaDaPosicao(pos.ticker, dia, pos.quantidade + qc, qv)

    custo_dt = custo_c / qc * casada
    valor_dt, custos_dt = valor_v / qv * casada, custos_v / qv * casada
    resultado_dt = valor_dt - custos_dt - custo_dt
    pos.resultado_realizado += resultado_dt
    saida = [
        VendaRealizada(pos.ticker, dia, casada, valor_dt, custos_dt, custo_dt, resultado_dt, True)
    ]
    if qc > casada:
        _comprar(pos, dia, qc - casada, custo_c - custo_dt)
    if qv > casada:
        saida.append(_vender(pos, dia, qv - casada, valor_v - valor_dt, custos_v - custos_dt))
    return saida


@dataclass(frozen=True, slots=True)
class Fatia:
    chave: str
    valor: Decimal
    percentual: float


def alocacao(valores: dict[str, Decimal]) -> list[Fatia]:
    """Fatias por chave (ativo, setor ou tipo), da maior para a menor, em pontos percentuais."""
    total = sum(valores.values(), ZERO)
    if total <= 0:
        return []
    fatias = [Fatia(k, v, float(v / total * 100)) for k, v in valores.items() if v > 0]
    return sorted(fatias, key=lambda f: (-f.valor, f.chave))
