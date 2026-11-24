"""Modelos do domínio, independentes de banco e de fonte de dados."""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Literal

TipoAtivo = Literal["acao", "fii", "etf", "bdr"]
TipoProvento = Literal[
    "dividendo", "jcp", "rendimento", "bonificacao", "desdobramento", "grupamento"
]
EVENTOS_SOCIETARIOS: frozenset[str] = frozenset({"bonificacao", "desdobramento", "grupamento"})


@dataclass(frozen=True, slots=True)
class AtivoInfo:
    ticker: str
    nome: str
    tipo: TipoAtivo
    setor: str | None = None
    segmento: str | None = None
    logo_url: str | None = None


@dataclass(frozen=True, slots=True)
class Candle:
    data: date
    abertura: Decimal
    maxima: Decimal
    minima: Decimal
    fechamento: Decimal
    fechamento_ajustado: Decimal
    volume: int


@dataclass(frozen=True, slots=True)
class Provento:
    """Provento em dinheiro (R$ por cota) ou evento societário.

    Para eventos societários, `valor` é o fator multiplicador da quantidade de
    ações: desdobramento 1:2 -> 2; grupamento 10:1 -> 0.1.
    """

    tipo: TipoProvento
    data_com: date
    valor: Decimal
    data_pagamento: date | None = None

    @property
    def societario(self) -> bool:
        return self.tipo in EVENTOS_SOCIETARIOS


@dataclass(frozen=True, slots=True)
class Fundamentos:
    data_referencia: date
    pl: float | None = None
    pvp: float | None = None
    dy_12m: float | None = None
    roe: float | None = None
    margem_liquida: float | None = None
    div_liq_ebitda: float | None = None
    vpa: float | None = None
    lpa: float | None = None
    valor_mercado: Decimal | None = None
    extras: dict = field(default_factory=dict)
