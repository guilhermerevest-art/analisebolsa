"""Insights: frases educacionais geradas por regras fixas (Fase 2, seção 3.2 da spec).

Cada regra recebe o `Contexto` do ativo e devolve um `Insight` ou None. Os textos saem
de templates fixos com números formatados em pt-BR. Eles descrevem o que aconteceu nos
dados e explicam o conceito; nunca dizem o que fazer (Resolução CVM 20).
"""

import math
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Literal

import numpy as np
import pandas as pd

from dominio import formato as f
from dominio.metricas import PREGOES_ANO, Metricas

Categoria = Literal["tendencia", "momento", "volatilidade", "volume", "fundamentos", "proventos"]
Tom = Literal["positivo", "neutro", "atencao"]

PREGOES_MINIMOS = 200
LIQUIDEZ_MINIMA = 100_000.0
JANELA_CRUZAMENTO = 5
PREGOES_6M = 126


@dataclass(frozen=True)
class Insight:
    codigo: str
    categoria: Categoria
    tom: Tom
    prioridade: int  # maior aparece primeiro
    titulo: str
    texto: str
    dados: dict = field(default_factory=dict)


@dataclass
class Contexto:
    """`cotacoes`: fechamento e volume por data crescente (a janela da análise).
    `indicadores`: mm50, mm200, rsi14, macd, macd_sinal, bb_superior, bb_inferior,
    vol_media20 no mesmo índice. `dy_anos`: DY (%) dos anos completos anteriores.
    `pl_pares`: P/L positivos das outras empresas do setor."""

    cotacoes: pd.DataFrame
    indicadores: pd.DataFrame
    metricas: Metricas
    setor: str | None = None
    dy_anos: list[float] = field(default_factory=list)
    pl_pares: list[float] = field(default_factory=list)

    @property
    def fechamento(self) -> pd.Series:
        return self.cotacoes["fechamento"].astype(float)

    def ind(self, coluna: str) -> pd.Series:
        return self.indicadores[coluna].reindex(self.cotacoes.index).astype(float)

    def ultimo(self, coluna: str) -> float | None:
        s = self.ind(coluna)
        v = float(s.iloc[-1]) if len(s) else math.nan
        return None if math.isnan(v) else v


def elegibilidade(pregoes: int, liquidez_20d: float | None) -> tuple[bool, str | None]:
    """Análise técnica só com histórico e liquidez mínimos (seção 3.3, Elegibilidade)."""
    if pregoes < PREGOES_MINIMOS:
        return False, (
            f"O ativo tem {pregoes} pregões de histórico, e a análise técnica pede pelo "
            f"menos {PREGOES_MINIMOS}."
        )
    liquidez = float(liquidez_20d or 0)
    if liquidez < LIQUIDEZ_MINIMA:
        return False, (
            f"A liquidez média é de {f.brl(liquidez)} por dia, abaixo do mínimo de "
            "R$ 100 mil usado para a análise técnica."
        )
    return True, None


def _cruzamento(a: pd.Series, b: pd.Series, janela: int) -> tuple[str, int] | None:
    """Cruzamento mais recente de `a` sobre `b` nos últimos `janela` pregões:
    ("alta" | "baixa", pregões atrás)."""
    sinal = np.sign((a - b).to_numpy())
    n = len(sinal)
    for i in range(n - 1, max(n - 1 - janela, 0), -1):
        atual, antes = sinal[i], sinal[i - 1]
        if np.isnan(atual) or np.isnan(antes):
            return None
        if atual != antes and atual != 0 and antes != 0:
            return ("alta" if atual > 0 else "baixa", n - 1 - i)
    return None


# regras técnicas


def cruzamento_medias(c: Contexto) -> Insight | None:
    r = _cruzamento(c.ind("mm50"), c.ind("mm200"), JANELA_CRUZAMENTO)
    if r is None:
        return None
    direcao, atras = r
    mm50, mm200 = c.ultimo("mm50"), c.ultimo("mm200")
    dados = {"mm50": mm50, "mm200": mm200, "pregoes_atras": atras}
    if direcao == "alta":
        return Insight(
            "cruzamento_mm50_mm200_alta", "tendencia", "positivo", 9,
            "Cruzamento de médias para cima",
            f"A média de 50 pregões ({f.brl(mm50)}) passou para cima da média de 200 "
            f"({f.brl(mm200)}) {f.quando(atras)}. Na análise técnica, esse movimento é chamado "
            "de golden cross e costuma ser lido como sinal de tendência de alta de prazo "
            "mais longo.",
            dados,
        )  # fmt: skip
    return Insight(
        "cruzamento_mm50_mm200_baixa", "tendencia", "atencao", 9,
        "Cruzamento de médias para baixo",
        f"A média de 50 pregões ({f.brl(mm50)}) passou para baixo da média de 200 "
        f"({f.brl(mm200)}) {f.quando(atras)}. Na análise técnica, esse movimento é chamado "
        "de death cross e costuma ser lido como sinal de tendência de baixa de prazo mais longo.",
        dados,
    )  # fmt: skip


def preco_mm200(c: Contexto) -> Insight | None:
    r = _cruzamento(c.fechamento, c.ind("mm200"), JANELA_CRUZAMENTO)
    if r is None:
        return None
    direcao, atras = r
    preco, mm200 = float(c.fechamento.iloc[-1]), c.ultimo("mm200")
    dados = {"preco": preco, "mm200": mm200, "pregoes_atras": atras}
    lado = "cima" if direcao == "alta" else "baixo"
    return Insight(
        "preco_mm200_acima" if direcao == "alta" else "preco_mm200_abaixo",
        "tendencia",
        "positivo" if direcao == "alta" else "atencao",
        8,
        f"Preço {'acima' if direcao == 'alta' else 'abaixo'} da média de 200 pregões",
        f"O fechamento ({f.brl(preco)}) passou para {lado} da média de 200 pregões "
        f"({f.brl(mm200)}) {f.quando(atras)}. Essa média resume a tendência de longo prazo, "
        "e muitos analistas observam de que lado dela o preço está.",
        dados,
    )


def distancia_mm200(c: Contexto) -> Insight | None:
    d = c.metricas.dist_mm200
    if d is None or abs(d) <= 20:
        return None
    return Insight(
        "distancia_mm200", "tendencia", "atencao", 6,
        "Preço distante da média de 200 pregões",
        f"O preço está {f.pct(abs(d))} {'acima' if d > 0 else 'abaixo'} da média de 200 "
        f"pregões ({f.brl(c.ultimo('mm200'))}). Distâncias maiores que 20% são pouco comuns e "
        "mostram um movimento forte em relação à tendência de longo prazo.",
        {"dist_mm200": d},
    )  # fmt: skip


def rsi(c: Contexto) -> Insight | None:
    v = c.ultimo("rsi14")
    if v is None or 30 <= v <= 70:
        return None
    if v > 70:
        return Insight(
            "rsi_sobrecompra", "momento", "atencao", 7,
            "RSI na faixa de sobrecompra",
            f"O RSI(14) está em {f.num(v, 0)}, acima de 70, faixa que a análise técnica chama "
            "de sobrecompra. O indicador compara o tamanho das altas e das quedas dos últimos "
            "14 pregões; valores altos mostram que as altas predominaram.",
            {"rsi14": v},
        )  # fmt: skip
    return Insight(
        "rsi_sobrevenda", "momento", "neutro", 7,
        "RSI na faixa de sobrevenda",
        f"O RSI(14) está em {f.num(v, 0)}, abaixo de 30, faixa que a análise técnica chama "
        "de sobrevenda. O indicador compara o tamanho das altas e das quedas dos últimos "
        "14 pregões; valores baixos mostram que as quedas predominaram.",
        {"rsi14": v},
    )  # fmt: skip


def macd(c: Contexto) -> Insight | None:
    r = _cruzamento(c.ind("macd"), c.ind("macd_sinal"), 1)
    if r is None:
        return None
    alta = r[0] == "alta"
    m, s = c.ultimo("macd"), c.ultimo("macd_sinal")
    return Insight(
        "macd_cruzamento_alta" if alta else "macd_cruzamento_baixa",
        "momento",
        "positivo" if alta else "atencao",
        6,
        f"MACD cruzou a linha de sinal para {'cima' if alta else 'baixo'}",
        f"No último pregão, o MACD ({f.num(m)}) passou para {'cima' if alta else 'baixo'} da "
        f"sua linha de sinal ({f.num(s)}). O MACD mede a diferença entre médias exponenciais "
        "curtas e longas, e esse cruzamento é lido como ganho de força "
        f"{'das altas' if alta else 'das quedas'} no curto prazo.",
        {"macd": m, "macd_sinal": s},
    )


def extremos_52s(c: Contexto) -> Insight | None:
    fech = c.fechamento
    ano = fech[fech.index > fech.index[-1] - pd.Timedelta(days=365)]
    if len(ano) < PREGOES_MINIMOS:
        return None
    preco = float(fech.iloc[-1])
    if ano.max() == ano.min():
        return None
    if preco >= float(ano.max()):
        return Insight(
            "maxima_52s", "momento", "positivo", 8,
            "Fechamento na máxima de 52 semanas",
            f"O fechamento de {f.brl(preco)} é o maior das últimas 52 semanas. Renovar a "
            "máxima mostra que o preço está acima de todos os fechamentos do último ano.",
            {"preco": preco},
        )  # fmt: skip
    if preco <= float(ano.min()):
        return Insight(
            "minima_52s", "momento", "atencao", 8,
            "Fechamento na mínima de 52 semanas",
            f"O fechamento de {f.brl(preco)} é o menor das últimas 52 semanas, abaixo de "
            "todos os fechamentos do último ano.",
            {"preco": preco},
        )  # fmt: skip
    return None


def bollinger_compressao(c: Contexto) -> Insight | None:
    largura = ((c.ind("bb_superior") - c.ind("bb_inferior")) / c.fechamento * 100).dropna()
    recente = largura.tail(PREGOES_6M)
    # estritamente abaixo dos 6 meses anteriores (bandas constantes não são compressão)
    if len(recente) < PREGOES_6M or largura.iloc[-1] >= recente.iloc[:-1].min():
        return None
    return Insight(
        "bollinger_compressao", "volatilidade", "neutro", 4,
        "Bandas de Bollinger estreitas",
        f"A distância entre as bandas de Bollinger ({f.pct(float(largura.iloc[-1]))} do preço) "
        "está no menor nível dos últimos 6 meses. As bandas acompanham a volatilidade dos "
        "últimos 20 pregões, e a análise técnica observa para que lado o preço se move depois "
        "de períodos de compressão.",
        {"largura_pct": float(largura.iloc[-1])},
    )  # fmt: skip


def bollinger_rompimento(c: Contexto) -> Insight | None:
    preco = float(c.fechamento.iloc[-1])
    sup, inf = c.ultimo("bb_superior"), c.ultimo("bb_inferior")
    if sup is None or inf is None or inf <= preco <= sup:
        return None
    lado = (
        f"acima da banda superior ({f.brl(sup)})"
        if preco > sup
        else f"abaixo da banda inferior ({f.brl(inf)})"
    )
    return Insight(
        "bollinger_rompimento", "volatilidade", "neutro", 5,
        "Fechamento fora das bandas de Bollinger",
        f"O fechamento ({f.brl(preco)}) ficou {lado}. As bandas ficam a dois desvios-padrão "
        "da média de 20 pregões, então um fechamento fora delas indica um movimento grande "
        "em relação à variação recente.",
        {"preco": preco, "bb_superior": sup, "bb_inferior": inf},
    )  # fmt: skip


def volume_anormal(c: Contexto) -> Insight | None:
    if len(c.cotacoes) < 21:
        return None
    volume = float(c.cotacoes["volume"].iloc[-1])
    media = float(c.cotacoes["volume"].astype(float).iloc[-21:-1].mean())
    if media <= 0 or volume <= 2.5 * media:
        return None
    vezes = volume / media
    dia = c.metricas.var_1d
    movimento = (
        ""
        if dia is None
        else f", num pregão de {'alta' if dia >= 0 else 'queda'} de {f.pct(abs(dia), 2)}"
    )
    return Insight(
        "volume_anormal", "volume", "neutro", 5,
        "Volume acima do normal",
        f"O volume do último pregão foi {f.num(vezes, 1)} vezes a média dos 20 pregões "
        f"anteriores{movimento}. Volume alto mostra mais participação dos investidores no "
        "movimento do dia.",
        {"vezes_media": vezes, "var_1d": dia},
    )  # fmt: skip


def volatilidade_alta(c: Contexto) -> Insight | None:
    v12 = c.metricas.volatilidade_12m
    retornos = np.log(c.fechamento / c.fechamento.shift(1)).dropna().tail(20)
    if not v12 or len(retornos) < 20:
        return None
    v20 = float(retornos.std(ddof=1)) * math.sqrt(PREGOES_ANO) * 100
    if v20 <= 1.5 * v12:
        return None
    return Insight(
        "volatilidade_alta", "volatilidade", "atencao", 5,
        "Volatilidade acima da média do ano",
        f"A volatilidade dos últimos 20 pregões ({f.pct(v20)} ao ano) é {f.num(v20 / v12, 1)} "
        f"vezes a volatilidade de 12 meses ({f.pct(v12)}). Isso significa oscilações diárias "
        "maiores que as habituais deste ativo.",
        {"volatilidade_20d": v20, "volatilidade_12m": v12},
    )  # fmt: skip


def tendencia(c: Contexto) -> Insight | None:
    t = c.metricas.tendencia
    mm50, mm200 = c.ultimo("mm50"), c.ultimo("mm200")
    if t is None or mm50 is None or mm200 is None:
        return None
    preco = float(c.fechamento.iloc[-1])
    dados = {"tendencia": t, "preco": preco, "mm50": mm50, "mm200": mm200}
    if t == "alta":
        return Insight(
            "tendencia", "tendencia", "positivo", 10, "Tendência de alta",
            f"O preço ({f.brl(preco)}) está acima da média de 50 pregões ({f.brl(mm50)}), que "
            f"está acima da média de 200 ({f.brl(mm200)}), e a média de 200 subiu nos últimos "
            "20 pregões. Esse alinhamento é a definição clássica de tendência de alta.",
            dados,
        )  # fmt: skip
    if t == "baixa":
        return Insight(
            "tendencia", "tendencia", "atencao", 10, "Tendência de baixa",
            f"O preço ({f.brl(preco)}) está abaixo da média de 50 pregões ({f.brl(mm50)}), que "
            f"está abaixo da média de 200 ({f.brl(mm200)}), e a média de 200 caiu nos últimos "
            "20 pregões. Esse alinhamento é a definição clássica de tendência de baixa.",
            dados,
        )  # fmt: skip
    if preco > mm50 > mm200 or preco < mm50 < mm200:
        sentido = "alta" if preco > mm50 else "baixa"
        mm200_foi = "não subiu" if sentido == "alta" else "não caiu"
        leitura = (
            f"O preço ({f.brl(preco)}) e as médias de 50 ({f.brl(mm50)}) e de 200 pregões "
            f"({f.brl(mm200)}) estão na ordem de uma tendência de {sentido}, mas a média de 200 "
            f"{mm200_foi} nos últimos 20 pregões."
        )
    else:
        leitura = (
            f"O preço ({f.brl(preco)}) e as médias de 50 ({f.brl(mm50)}) e de 200 pregões "
            f"({f.brl(mm200)}) não estão alinhados em uma direção."
        )
    return Insight(
        "tendencia", "tendencia", "neutro", 10, "Sem tendência definida",
        f"{leitura} Por isso, nesta leitura, o ativo está em tendência lateral: sem alta ou "
        "baixa definida no longo prazo.",
        dados,
    )  # fmt: skip


# regras de fundamentos (valem também para ativos sem a análise técnica)


def dy_historico(c: Contexto) -> Insight | None:
    dy = c.metricas.dy_12m
    anos = [v for v in c.dy_anos if v is not None]
    if dy is None or len(anos) < 3:
        return None
    media = sum(anos) / len(anos)
    if media <= 0 or dy <= media:
        return None
    return Insight(
        "dy_historico", "proventos", "positivo", 5,
        "Dividend yield acima da média do próprio ativo",
        f"O dividend yield dos últimos 12 meses é de {f.pct(dy, 2)}, acima da média de "
        f"{f.pct(media, 2)} dos últimos {len(anos)} anos. O valor considera os proventos já "
        "pagos e não indica quanto será distribuído daqui para frente.",
        {"dy_12m": dy, "media": media, "anos": len(anos)},
    )  # fmt: skip


def pl_setor(c: Contexto) -> Insight | None:
    pl = c.metricas.pl
    pares = [p for p in c.pl_pares if p and p > 0]
    if pl is None or pl <= 0 or len(pares) < 5:
        return None
    q1, mediana, q3 = (float(v) for v in np.percentile(pares, [25, 50, 75]))
    setor = c.setor or "da empresa"
    base = f"(mediana de {f.num(mediana, 1)} entre {len(pares)} outras empresas)"
    dados = {"pl": pl, "mediana": mediana, "pares": len(pares), "setor": c.setor}
    if pl <= q1:
        return Insight(
            "pl_setor", "fundamentos", "neutro", 4, "P/L baixo em relação ao setor",
            f"O P/L de {f.num(pl, 1)} está entre os 25% menores do setor {setor} {base}. Um P/L "
            "baixo significa que o preço é pequeno em relação ao lucro, o que pode refletir o "
            "que o mercado espera para os lucros futuros.",
            dados | {"posicao": "inferior"},
        )  # fmt: skip
    if pl >= q3:
        return Insight(
            "pl_setor", "fundamentos", "neutro", 4, "P/L alto em relação ao setor",
            f"O P/L de {f.num(pl, 1)} está entre os 25% maiores do setor {setor} {base}. Um P/L "
            "alto significa que o preço é grande em relação ao lucro, o que costuma refletir "
            "expectativa de crescimento dos lucros.",
            dados | {"posicao": "superior"},
        )  # fmt: skip
    return None


Regra = Callable[[Contexto], Insight | None]
REGRAS_TECNICAS: tuple[Regra, ...] = (
    tendencia, cruzamento_medias, preco_mm200, distancia_mm200, rsi, macd, extremos_52s,
    bollinger_compressao, bollinger_rompimento, volume_anormal, volatilidade_alta,
)  # fmt: skip
REGRAS_FUNDAMENTOS: tuple[Regra, ...] = (dy_historico, pl_setor)


def gerar_insights(c: Contexto) -> list[Insight]:
    elegivel, _ = elegibilidade(c.metricas.pregoes, c.metricas.volume_financeiro_20d)
    regras = (REGRAS_TECNICAS if elegivel else ()) + REGRAS_FUNDAMENTOS
    saida = [i for regra in regras if (i := regra(c)) is not None]
    return sorted(saida, key=lambda i: (-i.prioridade, i.codigo))
