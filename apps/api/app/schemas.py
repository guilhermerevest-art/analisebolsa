"""Modelos de resposta. Preços saem como string decimal; datas em ISO 8601."""

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, PlainSerializer

CENTAVO = Decimal("0.01")


def _decimal_str(d: Decimal) -> str:
    """Mantém 2 casas quando bastam (38.63) e mais quando o preço exige (0.1234)."""
    arredondado = d.quantize(CENTAVO)
    return format(arredondado if arredondado == d else d.normalize(), "f")


Preco = Annotated[Decimal, PlainSerializer(_decimal_str, return_type=str, when_used="json")]
TipoAtivo = Literal["acao", "fii", "etf", "bdr"]


class Problema(BaseModel):
    type: str = "about:blank"
    title: str
    status: int
    detail: str | None = None
    instance: str | None = None


class Health(BaseModel):
    status: Literal["ok"]
    banco: Literal["ok"]


class AtivoResumo(BaseModel):
    ticker: str
    nome: str
    tipo: TipoAtivo
    setor: str | None
    segmento: str | None
    logo_url: str | None


class PaginaAtivos(BaseModel):
    itens: list[AtivoResumo]
    pagina: int
    limite: int
    total: int


class UltimaCotacao(BaseModel):
    data: date
    abertura: Preco
    maxima: Preco
    minima: Preco
    fechamento: Preco
    volume: int


class Variacoes(BaseModel):
    """Variações percentuais. Dia usa o fechamento; 12 meses e ano usam o
    fechamento ajustado, que incorpora proventos."""

    dia: float | None
    doze_meses: float | None
    ano: float | None


class AtivoDetalhe(AtivoResumo):
    ultima_cotacao: UltimaCotacao | None
    variacoes: Variacoes


class Candle(BaseModel):
    data: date
    abertura: Preco
    maxima: Preco
    minima: Preco
    fechamento: Preco
    fechamento_ajustado: Preco
    volume: int


class Cotacoes(BaseModel):
    ticker: str
    periodo: Literal["1d", "1w", "1M"]
    candles: list[Candle]


class IndicadoresDia(BaseModel):
    data: date
    mm20: float | None
    mm50: float | None
    mm200: float | None
    mme9: float | None
    rsi14: float | None
    macd: float | None
    macd_sinal: float | None
    macd_hist: float | None
    bb_superior: float | None
    bb_inferior: float | None
    atr14: float | None
    vol_media20: float | None


class Indicadores(BaseModel):
    ticker: str
    itens: list[IndicadoresDia]


class FundamentosSnapshot(BaseModel):
    data_referencia: date
    pl: float | None
    pvp: float | None
    dy_12m: float | None
    roe: float | None
    margem_liquida: float | None
    div_liq_ebitda: float | None
    vpa: float | None
    lpa: float | None
    valor_mercado: Preco | None
    extras: dict


class Fundamentos(BaseModel):
    ticker: str
    ultimo: FundamentosSnapshot | None
    historico: list[FundamentosSnapshot]


class ProventoItem(BaseModel):
    tipo: Literal["dividendo", "jcp", "rendimento", "bonificacao", "desdobramento", "grupamento"]
    data_com: date
    data_pagamento: date | None
    valor: Annotated[
        Decimal, PlainSerializer(lambda d: format(d.normalize(), "f"), return_type=str)
    ]


class DyAno(BaseModel):
    ano: int
    total: Preco
    dy: float | None


class Proventos(BaseModel):
    ticker: str
    itens: list[ProventoItem]
    dy_por_ano: list[DyAno]


class Destaque(BaseModel):
    ticker: str
    nome: str
    tipo: TipoAtivo
    fechamento: Preco
    variacao: float


class Destaques(BaseModel):
    data: date | None
    altas: list[Destaque]
    baixas: list[Destaque]


class Execucao(BaseModel):
    execucao_id: int
    tipo: Literal["eod", "backfill", "catalogo", "fundamentos"]
    iniciado_em: datetime
    finalizado_em: datetime | None
    status: Literal["rodando", "ok", "parcial", "erro"]
    ativos_ok: int
    ativos_erro: int
    detalhes: dict


class Execucoes(BaseModel):
    itens: list[Execucao]
