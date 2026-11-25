"""Modelos de resposta. Preços saem como string decimal; datas em ISO 8601."""

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, Field, PlainSerializer

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
    tipo: Literal["eod", "backfill", "catalogo", "fundamentos", "analise"]
    iniciado_em: datetime
    finalizado_em: datetime | None
    status: Literal["rodando", "ok", "parcial", "erro"]
    ativos_ok: int
    ativos_erro: int
    detalhes: dict


class Execucoes(BaseModel):
    itens: list[Execucao]


# Fase 2: screener

Tendencia = Literal["alta", "baixa", "lateral"]


class MetricasAtivo(BaseModel):
    data: date
    preco: Preco
    var_1d: float | None
    var_1m: float | None
    var_3m: float | None
    var_6m: float | None
    var_12m: float | None
    var_ano: float | None
    volatilidade_12m: float | None
    drawdown_12m: float | None
    max_52s: Preco | None
    min_52s: Preco | None
    pos_52s: float | None
    dist_mm50: float | None
    dist_mm200: float | None
    rsi14: float | None
    tendencia: Tendencia | None
    volume_financeiro_20d: float | None
    pl: float | None
    pvp: float | None
    dy_12m: float | None
    roe: float | None
    margem_liquida: float | None
    div_liq_ebitda: float | None
    valor_mercado: float | None


class ItemScreener(MetricasAtivo):
    ticker: str
    nome: str
    tipo: TipoAtivo
    setor: str | None
    logo_url: str | None


class InsightAtivo(BaseModel):
    codigo: str
    categoria: Literal["tendencia", "momento", "volatilidade", "volume", "fundamentos", "proventos"]
    tom: Literal["positivo", "neutro", "atencao"]
    titulo: str
    texto: str
    data: date


class NivelPreco(BaseModel):
    preco: float
    tipo: Literal["suporte", "resistencia", "max_52s", "min_52s"]
    toques: int = Field(description="Quantos topos ou fundos semanais formaram o nível")


class CenarioPreco(BaseModel):
    tipo: Literal["alta", "lateral", "baixa"]
    titulo: str
    texto: str
    gatilho: float | None
    alvo: float | None
    invalidacao: float | None
    limite_inferior: float | None
    limite_superior: float | None
    dist_gatilho: float | None = Field(description="Distância do preço atual, em %")
    dist_alvo: float | None
    dist_invalidacao: float | None
    relacao: float | None = Field(
        description="Distância do gatilho ao alvo dividida pela do gatilho à invalidação"
    )


class CenariosAtivo(BaseModel):
    data: date
    atr14: float
    niveis: list[NivelPreco]
    cenarios: list[CenarioPreco]


class AnaliseAtivo(BaseModel):
    ticker: str
    elegivel: bool = Field(description="Se a análise técnica (insights técnicos e cenários) vale")
    motivo: str | None = Field(description="Por que a análise técnica não vale, se for o caso")
    metricas: MetricasAtivo | None
    insights: list[InsightAtivo]
    cenario: CenariosAtivo | None


class PaginaScreener(BaseModel):
    itens: list[ItemScreener]
    pagina: int
    limite: int
    total: int


class CampoScreener(BaseModel):
    campo: str
    rotulo: str
    unidade: Literal["pct", "brl", "numero"]
    grupo: Literal["preco", "tecnico", "fundamentos"]
    descricao: str
    min: float | None
    max: float | None


class CamposScreener(BaseModel):
    campos: list[CampoScreener]
    setores: list[str]
    tipos: list[TipoAtivo]


class ExemploSinal(BaseModel):
    ticker: str
    nome: str


class Sinal(BaseModel):
    codigo: str
    frase: str = Field(description='Completa "{total} ativos ..."')
    tom: Literal["positivo", "neutro", "atencao"]
    total: int
    exemplos: list[ExemploSinal]


class SinaisDoDia(BaseModel):
    data: date | None
    sinais: list[Sinal]


# Fase 3: usuário


class ItemWatchlist(BaseModel):
    ticker: str
    nome: str
    tipo: TipoAtivo
    setor: str | None
    logo_url: str | None
    adicionado_em: datetime
    metricas: MetricasAtivo | None


class Watchlist(BaseModel):
    itens: list[ItemWatchlist]
    limite: int


class EstadoWatchlist(BaseModel):
    ticker: str
    na_lista: bool


SerieIndice = Literal["cdi", "ipca", "ibov"]


class PontoIndice(BaseModel):
    data: date
    valor: float


class Indice(BaseModel):
    serie: SerieIndice
    unidade: Literal["pct_dia", "pct_mes", "pontos"]
    pontos: list[PontoIndice]


class Carteira(BaseModel):
    id: int
    nome: str
    criado_em: datetime
    operacoes: int


class Carteiras(BaseModel):
    itens: list[Carteira]
    limite: int


class NovaCarteira(BaseModel):
    nome: Annotated[str, Field(min_length=1, max_length=60)]


class NovaOperacao(BaseModel):
    ticker: Annotated[str, Field(pattern=r"^[A-Za-z0-9]{4,6}$")]
    tipo: Literal["compra", "venda"]
    data: date
    quantidade: Annotated[Decimal, Field(gt=0, max_digits=18, decimal_places=4)]
    preco: Annotated[Decimal, Field(gt=0, max_digits=14, decimal_places=4)]
    custos: Annotated[Decimal, Field(ge=0, max_digits=14, decimal_places=2)] = Decimal(0)


def _quantidade_str(d: Decimal) -> str:
    return format(d.normalize(), "f")


Quantidade = Annotated[Decimal, PlainSerializer(_quantidade_str, return_type=str, when_used="json")]


class OperacaoCarteira(BaseModel):
    id: int
    ticker: str
    nome: str
    tipo: Literal["compra", "venda"]
    data: date
    quantidade: Quantidade
    preco: Preco
    custos: Preco


class Operacoes(BaseModel):
    itens: list[OperacaoCarteira]


class PosicaoCarteira(BaseModel):
    ticker: str
    nome: str
    tipo: TipoAtivo
    setor: str | None
    quantidade: Quantidade
    preco_medio: Preco | None
    custo: Preco
    preco_atual: Preco | None
    data_preco: date | None
    valor_atual: Preco | None
    resultado: Preco | None
    variacao: float | None = Field(description="Valor atual sobre o custo, em %")
    proventos: Preco


class TotaisCarteira(BaseModel):
    patrimonio: Preco
    custo: Preco
    resultado_nao_realizado: Preco
    resultado_realizado: Preco
    proventos: Preco
    resultado_total: Preco


class FatiaAlocacao(BaseModel):
    chave: str
    valor: Preco
    percentual: float


class AlocacaoCarteira(BaseModel):
    ativo: list[FatiaAlocacao]
    setor: list[FatiaAlocacao]
    tipo: list[FatiaAlocacao]


class ProventoRecebido(BaseModel):
    ticker: str
    tipo: str
    data_com: date
    data_pagamento: date | None
    valor_unitario: Preco
    quantidade: Quantidade
    total: Preco


class ResumoCarteira(BaseModel):
    carteira: Carteira
    totais: TotaisCarteira
    posicoes: list[PosicaoCarteira]
    alocacao: AlocacaoCarteira
    proventos: list[ProventoRecebido]


class PontoRentabilidade(BaseModel):
    data: date
    patrimonio: float
    carteira: float = Field(description="Retorno acumulado (TWR) em %")
    cdi: float | None = Field(description="CDI acumulado no mesmo período, em %")
    ibov: float | None = Field(description="Ibovespa no mesmo período, em %")


class AcumuladoCarteira(BaseModel):
    data: date
    carteira: float
    cdi: float | None
    ibov: float | None


class RentabilidadeCarteira(BaseModel):
    inicio: date | None
    pontos: list[PontoRentabilidade]
    acumulado: AcumuladoCarteira | None


class PontoSimulacao(BaseModel):
    data: date = Field(description="Último dia do mês com dado")
    aportado: float
    patrimonio: float | None = Field(description="Valor no ativo; nulo sem ativo")
    proventos: float | None = Field(description="Proventos recebidos acumulados")
    cdi: float | None = Field(description="Mesmos aportes rendendo o CDI")
    ipca: float | None = Field(description="Mesmos aportes corrigidos pelo IPCA")


class PontoFaixa(BaseModel):
    data: date
    p10: float
    p50: float
    p90: float


class FaixaSimulada(BaseModel):
    trajetorias: int
    meses_historico: int = Field(description="Meses de retornos do ativo usados no sorteio")
    explicacao: str
    pontos: list[PontoFaixa]


class Simulacao(BaseModel):
    ticker: str | None
    inicio: date | None
    fim: date | None
    ipca_ate: date | None = Field(description="Último mês com IPCA publicado")
    pontos: list[PontoSimulacao]
    faixa: FaixaSimulada | None = Field(
        description="Faixa de resultados simulados; nula com menos de 5 anos de histórico"
    )
    aviso: str


TipoAlerta = Literal["preco_acima", "preco_abaixo", "variacao_dia", "insight"]


class NovoAlerta(BaseModel):
    ticker: Annotated[str, Field(pattern=r"^[A-Za-z0-9]{4,6}$")]
    tipo: TipoAlerta
    parametro: float | None = Field(
        default=None, gt=0, le=1e7, description="Preço em R$ ou variação em %; ignorado no insight"
    )
    codigo: str | None = Field(default=None, description="Código do sinal, no tipo insight")


class AlteracaoAlerta(BaseModel):
    ativo: bool = Field(description="Liga ou desliga o alerta")


class Alerta(BaseModel):
    id: int
    ticker: str
    nome: str
    tipo: TipoAlerta
    parametro: float | None
    codigo: str | None
    ativo: bool
    descricao: str
    ultimo_disparo: date | None
    criado_em: datetime


class DisparoAlerta(BaseModel):
    alerta_id: int
    ticker: str
    data: date
    texto: str
    enviado_em: datetime | None


class SinalAlerta(BaseModel):
    codigo: str
    descricao: str


class Alertas(BaseModel):
    itens: list[Alerta]
    limite: int
    ligados: int
    disparos: list[DisparoAlerta] = Field(description="Últimos disparos, do mais recente")
    sinais: list[SinalAlerta] = Field(description="Sinais que podem virar alerta")
