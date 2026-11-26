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


SerieIndice = Literal[
    "cdi", "ipca", "ibov", "dolar", "euro", "ifix", "smll", "idiv", "sp500", "bitcoin"
]
UnidadeIndice = Literal["pct_dia", "pct_mes", "pontos", "reais", "dolares"]


class PontoIndice(BaseModel):
    data: date
    valor: float


class Indice(BaseModel):
    serie: SerieIndice
    unidade: UnidadeIndice
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


class ArquivoImportacao(BaseModel):
    arquivo: Annotated[str, Field(max_length=3_000_000, description="O .xlsx em base64")]


class LinhaImportacao(BaseModel):
    linha: int = Field(description="Número da linha na planilha")
    data: date | None
    tipo: Literal["compra", "venda"] | None
    ticker: str | None
    quantidade: Quantidade | None
    preco: Preco | None
    situacao: Literal["nova", "duplicada", "ignorada"]
    motivo: str | None


class PreviaImportacao(BaseModel):
    linhas: list[LinhaImportacao]
    novas: int
    duplicadas: int
    ignoradas: int


class ResultadoImportacao(BaseModel):
    importadas: int
    duplicadas: int
    ignoradas: int


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


class MetricasBacktest(BaseModel):
    retorno_total: float = Field(description="Fração (0,1 = 10%)")
    retorno_anual: float | None = Field(description="Composto; nulo com menos de meio ano")
    volatilidade: float | None = Field(description="Anualizada")
    drawdown_maximo: float = Field(description="Maior queda desde um topo, fração negativa")
    sharpe: float | None = Field(description="Retorno acima do CDI dividido pela oscilação")
    exposicao: float | None = Field(default=None, description="Fração dos pregões posicionado")
    operacoes: int | None = None
    acertos: float | None = Field(
        default=None, description="Fração das operações encerradas com resultado positivo"
    )
    resultado_medio: float | None = Field(default=None, description="Por operação encerrada")


class ComparacaoBacktest(BaseModel):
    estrategia: MetricasBacktest
    buy_and_hold: MetricasBacktest
    cdi: MetricasBacktest


class PontoBacktest(BaseModel):
    data: date
    estrategia: float = Field(description="Patrimônio, base 100")
    buy_and_hold: float
    cdi: float
    drawdown: float = Field(description="% abaixo do topo da estratégia")
    drawdown_bh: float
    preco: float = Field(description="Fechamento ajustado por proventos usado no teste")


class OperacaoBacktest(BaseModel):
    entrada: date
    preco_entrada: float = Field(description="Preço ajustado, com deslizamento")
    saida: date | None = Field(description="Nula se a posição segue aberta no fim")
    preco_saida: float | None
    resultado: float = Field(description="Fração, líquida de custos")
    pregoes: int
    motivo: Literal["sinal", "stop", "aberta"]


class CustosBacktest(BaseModel):
    corretagem: float = Field(description="R$ por execução")
    taxas: float = Field(description="Fração do volume")
    deslizamento: float = Field(description="Fração do preço")
    total: float = Field(description="R$ gastos no período")


class Backtest(BaseModel):
    ticker: str
    estrategia: str
    nome: str
    regra: str
    parametros: dict[str, int]
    stop_atr: float | None
    capital: float
    custos: CustosBacktest
    cdi_no_caixa: bool
    inicio: date
    fim: date
    divisao: date = Field(description="Primeiro pregão fora da amostra (últimos 30%)")
    pontos: list[PontoBacktest]
    total: ComparacaoBacktest
    dentro_amostra: ComparacaoBacktest
    fora_amostra: ComparacaoBacktest
    operacoes: list[OperacaoBacktest]
    aviso: str


class AtivoPosicao(BaseModel):
    ticker: str
    data: date = Field(description="Último pregão")
    fechamento: float
    atr14: float | None


class AlvoPosicao(BaseModel):
    multiplo: int = Field(description="Distância até o stop multiplicada (1R, 2R, 3R)")
    preco: float


class Posicao(BaseModel):
    capital: float
    risco: float = Field(description="% do capital até o stop")
    entrada: float
    stop: float
    lote: int
    concentracao: float = Field(description="% máximo do capital na posição")
    ativo: AtivoPosicao | None
    quantidade: int
    valor: float
    pct_capital: float = Field(description="Fração")
    distancia_stop: float = Field(description="Fração do preço de entrada")
    perda_stop: float = Field(description="R$ perdidos se o stop for executado no preço")
    perda_pct_capital: float = Field(description="Fração")
    risco_maximo: float = Field(description="R$ permitidos pelo risco escolhido")
    limitada_por: Literal["concentracao", "capital"] | None
    alvos: list[AlvoPosicao]
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
    canais: list[Literal["email", "push", "whatsapp"]] = Field(
        description="Canais por onde o disparo já foi entregue"
    )


class SinalAlerta(BaseModel):
    codigo: str
    descricao: str


class Alertas(BaseModel):
    itens: list[Alerta]
    limite: int
    ligados: int
    disparos: list[DisparoAlerta] = Field(description="Últimos disparos, do mais recente")
    sinais: list[SinalAlerta] = Field(description="Sinais que podem virar alerta")


class AparelhoPush(BaseModel):
    id: int
    aparelho: str | None
    criado_em: datetime


class EstadoPush(BaseModel):
    disponivel: bool = Field(description="O servidor tem as chaves VAPID")
    chave_publica: str | None = Field(description="applicationServerKey para o navegador")
    aparelhos: list[AparelhoPush]


class EstadoWhatsApp(BaseModel):
    disponivel: bool = Field(description="O servidor tem a API do WhatsApp configurada")
    telefone: str | None = Field(description="Número mascarado, ex.: +55 (11) 9****-4321")
    confirmado: bool
    ativo: bool


class Notificacoes(BaseModel):
    push: EstadoPush
    whatsapp: EstadoWhatsApp


class ChavesPush(BaseModel):
    p256dh: Annotated[str, Field(min_length=20, max_length=200)]
    auth: Annotated[str, Field(min_length=8, max_length=100)]


class InscricaoPush(BaseModel):
    endpoint: Annotated[str, Field(pattern=r"^https://", max_length=1000)]
    keys: ChavesPush
    aparelho: Annotated[str | None, Field(max_length=80)] = None


class CancelamentoPush(BaseModel):
    endpoint: Annotated[str, Field(pattern=r"^https://", max_length=1000)]


class TestePush(BaseModel):
    enviados: int = Field(description="Aparelhos que receberam")


class NumeroWhatsApp(BaseModel):
    numero: Annotated[str, Field(min_length=8, max_length=30)]


class CodigoWhatsApp(BaseModel):
    codigo: Annotated[str, Field(pattern=r"^\s*\d{6}\s*$")]


class AlteracaoWhatsApp(BaseModel):
    ativo: bool = Field(description="Pausa ou retoma os alertas pelo WhatsApp")


class ConfigWhatsApp(BaseModel):
    configurada: bool
    url: str | None
    instancia: str | None
    chave_final: str | None = Field(description="Últimos 4 caracteres da API key, ex.: …a1b2")
    ativo: bool
    atualizado_em: datetime | None
    provedor_em_uso: Literal["evolution", "meta"] | None = Field(
        description="Por onde os alertas saem agora"
    )


class NovaConfigWhatsApp(BaseModel):
    url: Annotated[str, Field(min_length=8, max_length=300)]
    instancia: Annotated[str, Field(min_length=1, max_length=100, pattern=r"^[^/?#\s]+$")]
    chave: Annotated[str | None, Field(max_length=300)] = Field(
        default=None, description="API key; vazia mantém a guardada"
    )
    ativo: bool = True


class EstadoInstancia(BaseModel):
    estado: str = Field(description="open (conectada), connecting, close ou erro")
    qr: str | None = Field(description="QR code em data URL, quando não está conectada")
    codigo_pareamento: str | None
    erro: str | None


class TesteWhatsApp(BaseModel):
    numero: Annotated[str, Field(min_length=8, max_length=30)]


class MesImposto(BaseModel):
    mes: date = Field(description="Primeiro dia do mês de apuração")
    vendas_acoes: Preco = Field(description="Total vendido em ações (isenção até R$ 20 mil)")
    vendas_total: Preco
    isento_acoes: bool
    resultado_acoes: Preco
    ganho_isento: Preco = Field(description="Ganho em ações num mês isento")
    resultado_etf_bdr: Preco
    resultado_fii: Preco
    resultado_day_trade: Preco = Field(description="Day trade de ações, ETFs e BDRs")
    compensado: Preco = Field(description="Prejuízo de meses anteriores usado no mês")
    base_comum: Preco = Field(description="Base de ações, ETFs e BDRs (15%)")
    base_fii: Preco = Field(description="Base de FIIs (20%)")
    base_day_trade: Preco = Field(description="Base de day trade (20%)")
    imposto_devido: Preco
    irrf: Preco = Field(description="IRRF estimado do mês (0,005% das vendas)")
    irrf_usado: Preco
    acumulado_anterior: Preco = Field(description="DARF abaixo de R$ 10 de meses anteriores")
    darf: Preco = Field(description="Valor a pagar no mês (zero abaixo de R$ 10)")
    vencimento: date | None
    fica_para_depois: Preco
    prejuizo_comum: Preco = Field(description="Saldo de prejuízo de ações, ETFs e BDRs")
    prejuizo_fii: Preco
    prejuizo_day_trade: Preco


class AnoImposto(BaseModel):
    ano: int
    ganho_isento: Preco = Field(description="Ganhos isentos com ações no ano (para a declaração)")
    darf: Preco
    vendas: Preco


class PossivelDayTrade(BaseModel):
    ticker: str
    data: date


class ImpostoCarteira(BaseModel):
    meses: list[MesImposto] = Field(description="Meses com venda, do mais recente")
    anos: list[AnoImposto]
    prejuizo_comum: Preco
    prejuizo_fii: Preco
    prejuizo_day_trade: Preco
    pendente: Preco = Field(description="DARF abaixo de R$ 10 ainda não pago")
    saldo_irrf: Preco
    codigo_darf: str
    day_trade: list[PossivelDayTrade] = Field(
        description="Dias com compra e venda do mesmo ativo, apurados como day trade"
    )
    aviso: str


class BemDeclaracao(BaseModel):
    ticker: str
    nome: str
    tipo: Literal["acao", "fii", "etf", "bdr"]
    grupo: str | None = Field(description="Grupo da ficha Bens e Direitos, quando fixo")
    codigo: str | None
    descricao_grupo: str
    quantidade_anterior: Quantidade = Field(description="Em 31/12 do ano anterior")
    custo_anterior: Preco
    quantidade: Quantidade = Field(description="Em 31/12 do ano")
    custo: Preco
    discriminacao: str = Field(description="Texto pronto para o campo Discriminação")


class RendimentoDeclaracao(BaseModel):
    ticker: str
    nome: str
    bruto: Preco
    ir: Preco = Field(description="IR retido na fonte (JCP: 15%)")
    liquido: Preco


class DeclaracaoCarteira(BaseModel):
    ano: int
    anos: list[int] = Field(description="Anos com operações, do mais recente")
    bens: list[BemDeclaracao]
    dividendos: list[RendimentoDeclaracao]
    rendimentos_fii: list[RendimentoDeclaracao]
    jcp: list[RendimentoDeclaracao]
    ganho_isento_acoes: Preco = Field(description="Ganhos com ações em meses isentos")
    darfs: Preco = Field(description="DARFs de renda variável apurados no ano")
    meses_com_venda: int
    aviso: str


class IndicadorMercado(BaseModel):
    serie: SerieIndice
    nome: str
    unidade: UnidadeIndice
    data: date
    valor: float
    var_dia: float | None = Field(description="Variação em % sobre o ponto anterior")
    var_ano: float | None = Field(description="Variação em % no ano")
    var_12m: float | None = Field(description="Variação em % em 12 meses")
    pontos: list[PontoIndice] = Field(description="Um ponto por semana nos últimos 12 meses")


class IndicadoresMercado(BaseModel):
    itens: list[IndicadorMercado]
