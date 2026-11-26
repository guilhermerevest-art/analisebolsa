"""Dados da carteira para a declaração anual do IRPF (puro).

- Bens e Direitos: posição em 31/12 do ano anterior e do ano, pelo custo de aquisição
  (preço médio da Receita), por ativo.
- Rendimentos isentos: dividendos e rendimentos de FII pagos no ano.
- Tributação exclusiva: JCP pago no ano (bruto, IR de 15% retido na fonte e líquido).

O ano de um provento é o do pagamento (ou da data-com, se o pagamento não é conhecido).
"""

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from dominio.carteira import Operacao, consolidar
from dominio.modelos import Provento

ZERO = Decimal(0)
CENTAVO = Decimal("0.01")
ALIQUOTA_JCP = Decimal("0.15")

# Grupo e código da ficha Bens e Direitos; None quando o código depende do produto.
GRUPOS = {
    "acao": ("03", "01", "Participações societárias: ações"),
    "fii": ("07", "03", "Fundos: fundo de investimento imobiliário (FII)"),
    "etf": (None, None, "Fundos: fundo de índice (ETF)"),
    "bdr": (None, None, "Ativos negociados em bolsa: BDR"),
}


def _r(v: Decimal) -> Decimal:
    return v.quantize(CENTAVO, ROUND_HALF_UP)


def _qtd(q: Decimal) -> str:
    texto = f"{q.normalize():f}"
    if "." in texto:
        inteiro, frac = texto.split(".")
        return f"{int(inteiro):,}".replace(",", ".") + "," + frac
    return f"{int(texto):,}".replace(",", ".")


def _reais(v: Decimal) -> str:
    inteiro, frac = f"{_r(v):.2f}".split(".")
    return f"R$ {int(inteiro):,}".replace(",", ".") + f",{frac}"


@dataclass(frozen=True, slots=True)
class Bem:
    ticker: str
    nome: str
    tipo: str
    grupo: str | None
    codigo: str | None
    descricao_grupo: str
    quantidade_anterior: Decimal
    custo_anterior: Decimal
    quantidade: Decimal
    custo: Decimal
    discriminacao: str


@dataclass(frozen=True, slots=True)
class Rendimento:
    ticker: str
    nome: str
    bruto: Decimal
    ir: Decimal = ZERO

    @property
    def liquido(self) -> Decimal:
        return self.bruto - self.ir


@dataclass(frozen=True, slots=True)
class Declaracao:
    ano: int
    bens: list[Bem]
    dividendos: list[Rendimento]
    rendimentos_fii: list[Rendimento]
    jcp: list[Rendimento]


def _posicoes(ops: list[Operacao], eventos: dict[str, list[Provento]], ate: date) -> dict:
    validas = [o for o in ops if o.data <= ate]
    return consolidar(validas, eventos, ate=ate).posicoes if validas else {}


def montar(
    ops: list[Operacao],
    proventos: dict[str, list[Provento]],
    cadastro: dict[str, tuple[str, str]],
    ano: int,
) -> Declaracao:
    """`cadastro`: ticker -> (nome, tipo)."""
    eventos = {t: [p for p in ps if p.societario] for t, ps in proventos.items()}
    antes = _posicoes(ops, eventos, date(ano - 1, 12, 31))
    fim = _posicoes(ops, eventos, date(ano, 12, 31))

    bens: list[Bem] = []
    for ticker in sorted(set(antes) | set(fim)):
        a, f = antes.get(ticker), fim.get(ticker)
        qa, ca = (a.quantidade, a.custo) if a else (ZERO, ZERO)
        qf, cf = (f.quantidade, f.custo) if f else (ZERO, ZERO)
        if qa == 0 and qf == 0:
            continue
        nome, tipo = cadastro.get(ticker, (ticker, "acao"))
        grupo, codigo, desc = GRUPOS.get(tipo, GRUPOS["acao"])
        unidade = "cotas" if tipo in ("fii", "etf") else "ações" if tipo == "acao" else "BDRs"
        if qf > 0:
            texto = (
                f"{_qtd(qf)} {unidade} de {nome} ({ticker}), negociadas na B3, "
                f"preço médio de {_reais(cf / qf)}. Custo total de aquisição: {_reais(cf)}."
            )
        else:
            texto = f"{unidade.capitalize()} de {nome} ({ticker}), vendidas em {ano}."
        bens.append(Bem(ticker, nome, tipo, grupo, codigo, desc, qa, _r(ca), qf, _r(cf), texto))

    # Proventos em dinheiro do ano, com a quantidade em custódia na data-com.
    todos = consolidar(ops, proventos).proventos if ops else []
    soma: dict[tuple[str, str], Decimal] = defaultdict(Decimal)
    for p in todos:
        quando = p.data_pagamento or p.data_com
        if quando.year == ano:
            soma[(p.tipo, p.ticker)] += p.total

    def lista(tipo: str, com_ir: bool = False) -> list[Rendimento]:
        saida = []
        for (t, ticker), bruto in sorted(soma.items()):
            if t != tipo or bruto <= 0:
                continue
            nome = cadastro.get(ticker, (ticker, ""))[0]
            ir = _r(bruto * ALIQUOTA_JCP) if com_ir else ZERO
            saida.append(Rendimento(ticker, nome, _r(bruto), ir))
        return saida

    return Declaracao(ano, bens, lista("dividendo"), lista("rendimento"), lista("jcp", True))
