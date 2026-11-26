"""Backtest de estratégias por regras num ativo (puro, sem I/O).

Regras de execução (seção 2.3 da spec da Fase 4):
- O sinal usa só dados até o fechamento do pregão t e é executado na abertura de t+1.
- Os indicadores são calculados sobre todo o histórico carregado, inclusive antes do início
  do período, então o aquecimento não consome o período testado. Um indicador em t depende
  só de dados até t.
- Só posição comprada, com todo o patrimônio, em quantidade fracionária (sem lotes).
- Custos em toda execução: corretagem fixa, taxas sobre o volume e deslizamento contra o
  usuário (a entrada sai mais cara e a saída, mais barata).
- Fora da posição, o caixa pode render o CDI do dia.
- Os preços chegam ajustados por proventos e eventos (o fator do dia multiplica abertura,
  máxima, mínima e fechamento), o que equivale a reinvestir os proventos.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date
from math import sqrt

import numpy as np
import pandas as pd

from dominio.indicadores import atr, bollinger, macd, mm, mme, rsi

PREGOES_ANO = 252
PREGOES_MINIMOS = 250  # um ano no período testado
FRACAO_DENTRO = 0.7
PONTOS_MAXIMOS = 1000

AVISO = (
    "Exercício sobre dados históricos, com custos estimados e sem impostos. Resultado "
    "simulado não garante resultado futuro, e regras ajustadas ao passado costumam piorar "
    "fora dele. Não é recomendação de investimento."
)


@dataclass(frozen=True, slots=True)
class Parametro:
    chave: str
    rotulo: str
    minimo: int
    maximo: int
    padrao: int


@dataclass(frozen=True, slots=True)
class Estrategia:
    codigo: str
    nome: str
    regra: str  # texto com {chave} para cada parâmetro
    parametros: tuple[Parametro, ...] = ()


ESTRATEGIAS: dict[str, Estrategia] = {
    e.codigo: e
    for e in (
        Estrategia(
            "cruzamento_mm",
            "Cruzamento de médias móveis",
            "Entrada quando a média de {curta} pregões cruza para cima a de {longa}; saída "
            "quando cruza para baixo.",
            (
                Parametro("curta", "Média curta (pregões)", 5, 100, 20),
                Parametro("longa", "Média longa (pregões)", 20, 250, 100),
            ),
        ),
        Estrategia(
            "rsi",
            "IFR (RSI)",
            "Entrada quando o IFR de {rsi_periodo} pregões fecha abaixo de {rsi_entrada}; "
            "saída quando fecha acima de {rsi_saida}.",
            (
                Parametro("rsi_periodo", "Período do IFR (pregões)", 2, 30, 14),
                Parametro("rsi_entrada", "Entrada abaixo de", 5, 50, 30),
                Parametro("rsi_saida", "Saída acima de", 50, 95, 70),
            ),
        ),
        Estrategia(
            "macd",
            "Cruzamento do MACD",
            "Entrada quando o MACD ({macd_rapida}, {macd_lenta}) cruza para cima a sua média "
            "de {macd_sinal}; saída quando cruza para baixo.",
            (
                Parametro("macd_rapida", "Média rápida (pregões)", 5, 50, 12),
                Parametro("macd_lenta", "Média lenta (pregões)", 10, 100, 26),
                Parametro("macd_sinal", "Linha de sinal (pregões)", 3, 30, 9),
            ),
        ),
        Estrategia(
            "bollinger",
            "Bandas de Bollinger",
            "Entrada quando o fechamento fica abaixo da banda inferior ({bb_periodo} pregões, "
            "{bb_desvios} desvios); saída quando volta acima da média.",
            (
                Parametro("bb_periodo", "Período (pregões)", 10, 50, 20),
                Parametro("bb_desvios", "Desvios-padrão", 1, 3, 2),
            ),
        ),
        Estrategia(
            "setup_91",
            "Setup 9.1",
            "Entrada quando a média exponencial de {mme_periodo} pregões vira para cima; saída "
            "quando vira para baixo.",
            (Parametro("mme_periodo", "Média exponencial (pregões)", 5, 50, 9),),
        ),
        Estrategia(
            "rompimento",
            "Rompimento de máxima",
            "Entrada quando o fechamento passa da máxima dos {n_entrada} pregões anteriores; "
            "saída quando fica abaixo da mínima dos {n_saida} anteriores.",
            (
                Parametro("n_entrada", "Máxima de (pregões)", 10, 250, 55),
                Parametro("n_saida", "Mínima de (pregões)", 5, 100, 20),
            ),
        ),
        Estrategia(
            "buy_and_hold",
            "Manter o ativo (buy and hold)",
            "Entrada na abertura do primeiro pregão e nenhuma saída.",
        ),
    )
}


class ParametrosInvalidos(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class Custos:
    corretagem: float = 0.0  # R$ por execução
    taxas: float = 0.0003  # fração do volume
    deslizamento: float = 0.0005  # fração do preço, contra o usuário


@dataclass(frozen=True, slots=True)
class Config:
    estrategia: str
    parametros: dict[str, int] = field(default_factory=dict)
    stop_atr: float | None = None  # múltiplo do ATR14 na entrada
    custos: Custos = Custos()
    capital: float = 10_000.0
    cdi_no_caixa: bool = True


def validar(estrategia: str, parametros: dict[str, int | None]) -> dict[str, int]:
    """Preenche os padrões e confere os limites. Levanta ParametrosInvalidos."""
    e = ESTRATEGIAS.get(estrategia)
    if e is None:
        raise ParametrosInvalidos("estratégia desconhecida")
    saida: dict[str, int] = {}
    for p in e.parametros:
        valor = parametros.get(p.chave)
        valor = p.padrao if valor is None else int(valor)
        if not p.minimo <= valor <= p.maximo:
            raise ParametrosInvalidos(f"{p.chave} deve ficar entre {p.minimo} e {p.maximo}")
        saida[p.chave] = valor
    if estrategia == "cruzamento_mm" and saida["curta"] >= saida["longa"]:
        raise ParametrosInvalidos("a média curta precisa ser menor que a longa")
    if estrategia == "macd" and saida["macd_rapida"] >= saida["macd_lenta"]:
        raise ParametrosInvalidos("a média rápida do MACD precisa ser menor que a lenta")
    return saida


def descrever(estrategia: str, parametros: dict[str, int]) -> str:
    return ESTRATEGIAS[estrategia].regra.format(**parametros)


# Sinais


def sinais(estrategia: str, p: dict[str, int], df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """(entrada, saida) booleanos por pregão, cada um calculado só com dados até o pregão.

    `df` tem as colunas abertura, maxima, minima e fechamento, em ordem de data. Antes do
    aquecimento os dois ficam falsos.
    """
    fech = df["fechamento"]
    if estrategia == "cruzamento_mm":
        entrada, saida = _cruzamento(mm(fech, p["curta"]), mm(fech, p["longa"]))
    elif estrategia == "macd":
        linha, sinal, _ = macd(fech, p["macd_rapida"], p["macd_lenta"], p["macd_sinal"])
        entrada, saida = _cruzamento(linha, sinal)
    elif estrategia == "bollinger":
        _, inferior = bollinger(fech, p["bb_periodo"], p["bb_desvios"])
        media = mm(fech, p["bb_periodo"])
        entrada = fech < inferior
        saida = fech > media
    elif estrategia == "setup_91":
        m = mme(fech, p["mme_periodo"])
        delta = m.diff()
        sobe, cai = delta > 0, delta < 0
        valido = delta.notna() & delta.shift(1).notna()
        entrada = valido & sobe & (delta.shift(1) <= 0)
        saida = valido & cai & (delta.shift(1) >= 0)
    elif estrategia == "rsi":
        r = rsi(fech, p["rsi_periodo"])
        entrada = r < p["rsi_entrada"]
        saida = r > p["rsi_saida"]
    elif estrategia == "rompimento":
        teto = df["maxima"].rolling(p["n_entrada"], min_periods=p["n_entrada"]).max().shift(1)
        piso = df["minima"].rolling(p["n_saida"], min_periods=p["n_saida"]).min().shift(1)
        entrada = fech > teto
        saida = fech < piso
    elif estrategia == "buy_and_hold":
        entrada = pd.Series(False, index=df.index)
        saida = entrada
    else:  # pragma: no cover (validado antes)
        raise ParametrosInvalidos("estratégia desconhecida")
    return entrada.fillna(False).to_numpy(bool), saida.fillna(False).to_numpy(bool)


def _cruzamento(rapida: pd.Series, lenta: pd.Series) -> tuple[pd.Series, pd.Series]:
    """Cruzamento para cima (entrada) e para baixo (saída), só com as duas séries válidas
    no pregão e no anterior."""
    acima = rapida > lenta
    valido = rapida.notna() & lenta.notna() & rapida.shift(1).notna() & lenta.shift(1).notna()
    anterior = acima.shift(1, fill_value=False)
    return valido & acima & ~anterior, valido & ~acima & anterior


def aquecimento(estrategia: str, p: dict[str, int], stop_atr: float | None) -> int:
    """Pregões de histórico que os indicadores precisam antes do primeiro sinal."""
    base = {
        "cruzamento_mm": lambda: p["longa"] + 1,
        "rsi": lambda: p["rsi_periodo"] + 1,
        "macd": lambda: p["macd_lenta"] + p["macd_sinal"] + 1,
        "bollinger": lambda: p["bb_periodo"],
        "setup_91": lambda: p["mme_periodo"] + 2,
        "rompimento": lambda: max(p["n_entrada"], p["n_saida"]) + 1,
        "buy_and_hold": lambda: 0,
    }[estrategia]()
    return max(base, 15 if stop_atr else 0)


# Simulação


@dataclass(frozen=True, slots=True)
class Operacao:
    entrada: date
    preco_entrada: float  # já com deslizamento
    saida: date | None  # None: ainda aberta no fim do período
    preco_saida: float | None
    resultado: float  # fração, líquida de custos (marcada a mercado se aberta)
    pregoes: int
    motivo: str  # sinal, stop ou aberta


@dataclass(frozen=True, slots=True)
class Execucao:
    datas: list[date]
    patrimonio: np.ndarray  # fim de cada pregão
    posicionado: np.ndarray  # bool, no fechamento
    operacoes: list[Operacao]
    custos: float


def executar(
    df: pd.DataFrame,
    inicio: int,
    entrada: np.ndarray,
    saida: np.ndarray,
    cdi: np.ndarray,
    config: Config,
    atr14: np.ndarray | None = None,
    entrar_no_primeiro: bool = False,
) -> Execucao:
    """Roda a estratégia nos pregões `df[inicio:]`; `cdi` é a taxa diária (fração) por pregão."""
    abertura = df["abertura"].to_numpy(float)
    fechamento = df["fechamento"].to_numpy(float)
    datas = list(df.index)
    c = config.custos
    n = len(df)

    caixa, qtd = config.capital, 0.0
    custos = 0.0
    ordem: str | None = "entrar" if entrar_no_primeiro else None
    motivo_ordem = ""
    stop: float | None = None
    aberta: dict | None = None  # entrada em andamento
    operacoes: list[Operacao] = []
    patrimonio = np.empty(n - inicio)
    posicionado = np.zeros(n - inicio, bool)

    for k, i in enumerate(range(inicio, n)):
        # Abertura: executa a ordem decidida no fechamento anterior.
        if ordem == "entrar" and qtd == 0:
            preco = abertura[i] * (1 + c.deslizamento)
            investido = caixa
            qtd = max(caixa - c.corretagem, 0.0) / (preco * (1 + c.taxas))
            custos += qtd * preco * c.taxas + c.corretagem + qtd * abertura[i] * c.deslizamento
            caixa = 0.0
            aberta = {"data": datas[i], "preco": preco, "i": i, "investido": investido}
            if config.stop_atr and atr14 is not None:
                stop = preco - config.stop_atr * atr14[i - 1] if i > 0 else None
        elif ordem == "sair" and qtd > 0:
            preco = abertura[i] * (1 - c.deslizamento)
            bruto = qtd * preco
            custos += bruto * c.taxas + c.corretagem + qtd * abertura[i] * c.deslizamento
            caixa = bruto * (1 - c.taxas) - c.corretagem
            assert aberta is not None
            operacoes.append(
                Operacao(
                    aberta["data"],
                    aberta["preco"],
                    datas[i],
                    preco,
                    caixa / aberta["investido"] - 1,
                    i - aberta["i"],
                    motivo_ordem,
                )
            )
            qtd, aberta, stop = 0.0, None, None
        ordem = None

        # Fim do dia: caixa rende o CDI e o patrimônio é marcado no fechamento.
        if config.cdi_no_caixa and caixa > 0:
            caixa *= 1 + cdi[i]
        patrimonio[k] = caixa + qtd * fechamento[i]
        posicionado[k] = qtd > 0

        # Fechamento: decide a ordem da próxima abertura (só se houver próxima).
        if i + 1 >= n:
            continue
        if qtd == 0 and entrada[i]:
            ordem = "entrar"
        elif qtd > 0:
            if stop is not None and fechamento[i] < stop:
                ordem, motivo_ordem = "sair", "stop"
            elif saida[i]:
                ordem, motivo_ordem = "sair", "sinal"

    if aberta is not None:
        operacoes.append(
            Operacao(
                aberta["data"],
                aberta["preco"],
                None,
                None,
                patrimonio[-1] / aberta["investido"] - 1,
                n - 1 - aberta["i"],
                "aberta",
            )
        )
    return Execucao(datas[inicio:], patrimonio, posicionado, operacoes, custos)


# Métricas


@dataclass(frozen=True, slots=True)
class Metricas:
    retorno_total: float
    retorno_anual: float | None
    volatilidade: float | None
    drawdown_maximo: float
    sharpe: float | None
    exposicao: float | None = None
    operacoes: int | None = None
    acertos: float | None = None  # fração das operações encerradas com resultado positivo
    resultado_medio: float | None = None


def metricas(
    valores: np.ndarray,
    base: float,
    cdi: np.ndarray,
    posicionado: np.ndarray | None = None,
    operacoes: Sequence[Operacao] | None = None,
) -> Metricas:
    """`valores` é o patrimônio no fim de cada pregão e `base`, o valor antes do primeiro."""
    serie = np.concatenate([[base], valores])
    retornos = serie[1:] / serie[:-1] - 1
    dias = len(valores)
    total = serie[-1] / base - 1
    anual = (1 + total) ** (PREGOES_ANO / dias) - 1 if dias >= PREGOES_ANO / 2 else None
    vol = float(np.std(retornos, ddof=1) * sqrt(PREGOES_ANO)) if dias > 1 else None
    excesso = retornos - cdi[:dias]
    desvio = np.std(excesso, ddof=1) if dias > 1 else 0.0
    sharpe = float(np.mean(excesso) / desvio * sqrt(PREGOES_ANO)) if desvio > 1e-12 else None
    topo = np.maximum.accumulate(serie)
    dd = float(np.min(serie / topo - 1))
    extras: dict = {}
    if posicionado is not None:
        extras["exposicao"] = float(np.mean(posicionado))
    if operacoes is not None:
        encerradas = [o for o in operacoes if o.saida is not None]
        extras["operacoes"] = len(operacoes)
        if encerradas:
            extras["acertos"] = sum(o.resultado > 0 for o in encerradas) / len(encerradas)
            extras["resultado_medio"] = float(np.mean([o.resultado for o in encerradas]))
    return Metricas(float(total), anual, vol, dd, sharpe, **extras)


@dataclass(frozen=True, slots=True)
class Comparacao:
    estrategia: Metricas
    buy_and_hold: Metricas
    cdi: Metricas


@dataclass(frozen=True, slots=True)
class Ponto:
    data: date
    estrategia: float  # base 100
    buy_and_hold: float
    cdi: float
    drawdown: float  # % da estratégia abaixo do topo (<= 0)
    drawdown_bh: float
    preco: float  # fechamento ajustado usado no teste


@dataclass(frozen=True, slots=True)
class Resultado:
    inicio: date
    fim: date
    divisao: date  # primeiro pregão fora da amostra
    pontos: list[Ponto]
    total: Comparacao
    dentro: Comparacao
    fora: Comparacao
    operacoes: list[Operacao]
    custos: float
    regra: str


def _reduzir(datas: list[date], manter: set[date] = frozenset()) -> list[int]:
    """Índices a manter no gráfico: todos, ou o último pregão de cada semana se forem muitos.
    As datas de `manter` (entradas e saídas) ficam sempre, para as marcas caírem num ponto."""
    if len(datas) <= PONTOS_MAXIMOS:
        return list(range(len(datas)))
    return [
        i
        for i, d in enumerate(datas)
        if i + 1 == len(datas)
        or d in manter
        or datas[i + 1].isocalendar()[:2] != d.isocalendar()[:2]
    ]


def rodar(
    df: pd.DataFrame,
    inicio: date,
    fim: date,
    cdi_pct: dict[date, float],
    config: Config,
) -> Resultado | None:
    """Backtest em [inicio, fim]. `df` traz o histórico ajustado (pode começar antes de `inicio`
    para o aquecimento). Devolve None com menos de um ano de pregões testáveis."""
    df = df[df.index <= fim].sort_index()
    p = validar(config.estrategia, config.parametros)
    aquec = aquecimento(config.estrategia, p, config.stop_atr)
    primeiro = int(np.searchsorted(np.array(df.index, dtype=object), inicio, side="left"))
    primeiro = max(primeiro, aquec)
    n = len(df)
    if n - primeiro < PREGOES_MINIMOS:
        return None

    cdi = np.array([cdi_pct.get(d, 0.0) / 100 for d in df.index])
    atr14 = atr(df["maxima"], df["minima"], df["fechamento"]).to_numpy(float)
    entrada, saida = sinais(config.estrategia, p, df)
    bh = config.estrategia == "buy_and_hold"
    ex = executar(df, primeiro, entrada, saida, cdi, config, atr14, entrar_no_primeiro=bh)
    cfg_bh = Config("buy_and_hold", custos=config.custos, capital=config.capital)
    nada = np.zeros(n, bool)
    ex_bh = executar(df, primeiro, nada, nada, cdi, cfg_bh, entrar_no_primeiro=True)
    cdi_janela = cdi[primeiro:]
    cdi_valores = config.capital * np.cumprod(1 + cdi_janela)

    def comparar(a: int, b: int) -> Comparacao:
        def base(valores: np.ndarray) -> float:
            return config.capital if a == 0 else float(valores[a - 1])

        ops = [o for o in ex.operacoes if ex.datas[a] <= o.entrada <= ex.datas[b - 1]]
        return Comparacao(
            metricas(ex.patrimonio[a:b], base(ex.patrimonio), cdi_janela[a:b],
                     ex.posicionado[a:b], ops),
            metricas(ex_bh.patrimonio[a:b], base(ex_bh.patrimonio), cdi_janela[a:b],
                     ex_bh.posicionado[a:b]),
            metricas(cdi_valores[a:b], base(cdi_valores), cdi_janela[a:b]),
        )  # fmt: skip

    total = len(ex.datas)
    corte = int(total * FRACAO_DENTRO)

    def drawdown(valores: np.ndarray) -> np.ndarray:
        serie = np.concatenate([[config.capital], valores])
        return (serie / np.maximum.accumulate(serie) - 1)[1:] * 100

    dd, dd_bh = drawdown(ex.patrimonio), drawdown(ex_bh.patrimonio)
    escala = 100 / config.capital
    fechamento = df["fechamento"].to_numpy(float)[primeiro:]
    marcas = {o.entrada for o in ex.operacoes} | {o.saida for o in ex.operacoes if o.saida}
    pontos = [
        Ponto(
            ex.datas[i],
            round(float(ex.patrimonio[i]) * escala, 2),
            round(float(ex_bh.patrimonio[i]) * escala, 2),
            round(float(cdi_valores[i]) * escala, 2),
            round(float(dd[i]), 2),
            round(float(dd_bh[i]), 2),
            round(float(fechamento[i]), 4),
        )
        for i in _reduzir(ex.datas, marcas)
    ]
    return Resultado(
        ex.datas[0],
        ex.datas[-1],
        ex.datas[corte],
        pontos,
        comparar(0, total),
        comparar(0, corte),
        comparar(corte, total),
        ex.operacoes,
        round(ex.custos, 2),
        descrever(config.estrategia, p),
    )


def ajustar(df: pd.DataFrame) -> pd.DataFrame:
    """Multiplica abertura, máxima, mínima e fechamento pelo fator de proventos do dia
    (`fechamento_ajustado / fechamento`)."""
    fator = df["fechamento_ajustado"] / df["fechamento"]
    return pd.DataFrame(
        {col: df[col] * fator for col in ("abertura", "maxima", "minima", "fechamento")},
        index=df.index,
    )
