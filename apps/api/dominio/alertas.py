"""Alertas: avalia regras contra o pregão do dia e escreve o fato (puro, sem I/O).

Os textos descrevem o que aconteceu, nunca uma ação.
"""

from dataclasses import dataclass
from datetime import date

from dominio.formato import num

TIPOS = ("preco_acima", "preco_abaixo", "variacao_dia", "insight")

# Sinais factuais da Fase 2 que podem virar alerta, com a frase no singular.
INSIGHTS_ALERTA: dict[str, str] = {
    "maxima_52s": "renovou a máxima de 52 semanas",
    "minima_52s": "renovou a mínima de 52 semanas",
    "cruzamento_mm50_mm200_alta": "teve a MM50 cruzando a MM200 para cima",
    "cruzamento_mm50_mm200_baixa": "teve a MM50 cruzando a MM200 para baixo",
    "preco_mm200_acima": "passou para cima da média de 200 pregões",
    "preco_mm200_abaixo": "passou para baixo da média de 200 pregões",
    "rsi_sobrecompra": "ficou com RSI acima de 70",
    "rsi_sobrevenda": "ficou com RSI abaixo de 30",
    "volume_anormal": "negociou mais de 2,5 vezes o volume médio",
    "macd_cruzamento_alta": "teve o MACD cruzando a linha de sinal para cima",
    "macd_cruzamento_baixa": "teve o MACD cruzando a linha de sinal para baixo",
}


@dataclass(frozen=True, slots=True)
class Regra:
    ticker: str
    tipo: str
    parametro: float | None = None
    codigo: str | None = None


@dataclass(frozen=True, slots=True)
class Pregao:
    data: date
    fechamento: float
    anterior: float | None  # fechamento do pregão anterior
    insights: frozenset[str] = frozenset()

    @property
    def variacao_dia(self) -> float | None:
        return (self.fechamento / self.anterior - 1) * 100 if self.anterior else None


def _reais(v: float) -> str:
    return f"R$ {num(v, 2)}"


def _pct(v: float) -> str:
    return f"{'+' if v > 0 else '−' if v < 0 else ''}{num(abs(v), 2)}%"


def descrever(regra: Regra) -> str:
    """Descrição da regra para listas e notificações."""
    if regra.tipo == "preco_acima":
        return f"Fechamento acima de {_reais(regra.parametro)}"
    if regra.tipo == "preco_abaixo":
        return f"Fechamento abaixo de {_reais(regra.parametro)}"
    if regra.tipo == "variacao_dia":
        return f"Variação do dia maior que {num(regra.parametro, 2)}% (alta ou queda)"
    return f"Sinal: {INSIGHTS_ALERTA[regra.codigo]}"


def avaliar(regra: Regra, pregao: Pregao) -> str | None:
    """Texto do disparo, ou None se a regra não disparou nesse pregão.

    Os alertas de preço disparam quando o fechamento cruza o valor (o anterior estava do outro
    lado ou não existe), para não repetir todo dia enquanto o preço fica além dele.
    """
    t, d = regra.ticker, f"{pregao.data:%d/%m/%Y}"
    ant = pregao.anterior
    if (
        regra.tipo == "preco_acima"
        and pregao.fechamento > regra.parametro
        and (ant is None or ant <= regra.parametro)
    ):
        return (
            f"{t} fechou acima de {_reais(regra.parametro)} em {d}, a {_reais(pregao.fechamento)}."
        )
    if (
        regra.tipo == "preco_abaixo"
        and pregao.fechamento < regra.parametro
        and (ant is None or ant >= regra.parametro)
    ):
        return (
            f"{t} fechou abaixo de {_reais(regra.parametro)} em {d}, a {_reais(pregao.fechamento)}."
        )
    if (
        regra.tipo == "variacao_dia"
        and pregao.variacao_dia is not None
        and abs(pregao.variacao_dia) > regra.parametro
    ):
        return (
            f"{t} variou {_pct(pregao.variacao_dia)} no pregão de {d}, "
            f"mais que os {num(regra.parametro, 2)}% do alerta."
        )
    if regra.tipo == "insight" and regra.codigo in pregao.insights:
        return f"{t} {INSIGHTS_ALERTA[regra.codigo]} no pregão de {d}."
    return None


@dataclass(frozen=True, slots=True)
class Disparo:
    ticker: str
    data: date
    texto: str


AVISO = "Conteúdo educacional, não é recomendação de investimento."

# A Meta limita cada variável de modelo a 1.024 caracteres e não aceita quebra de linha.
LIMITE_WHATSAPP = 900


def compor_push(disparos: list[Disparo]) -> dict[str, str]:
    """Título, corpo e caminho da notificação push de um usuário."""
    n = len(disparos)
    titulo = "1 alerta disparado" if n == 1 else f"{n} alertas disparados"
    corpo = disparos[0].texto + (f" E mais {n - 1}." if n > 1 else "")
    url = f"/ativo/{disparos[0].ticker}" if n == 1 else "/alertas"
    return {"titulo": titulo, "corpo": corpo, "url": url}


def compor_whatsapp(disparos: list[Disparo]) -> str:
    """Textos do dia numa linha só, para a variável {{1}} do modelo `alertas_disparados`."""
    partes: list[str] = []
    for i, d in enumerate(disparos):
        resto = len(disparos) - i
        candidato = "; ".join([*partes, d.texto.rstrip(".")])
        sufixo = f"; e mais {resto - 1}" if resto > 1 else ""
        if partes and len(candidato) + len(sufixo) > LIMITE_WHATSAPP:
            return "; ".join(partes) + f"; e mais {resto}"
        partes.append(d.texto.rstrip("."))
    return " ".join("; ".join(partes).split())[:LIMITE_WHATSAPP]


def compor_mensagem_whatsapp(disparos: list[Disparo], link: str) -> str:
    """Mensagem livre (Evolution API): uma linha por disparo, com o link e o aviso."""
    itens = "\n".join(f"• {d.texto}" for d in disparos)
    cabecalho = (
        "Alerta do pregão no analisebolsa:"
        if len(disparos) == 1
        else (f"{len(disparos)} alertas do pregão no analisebolsa:")
    )
    return f"{cabecalho}\n\n{itens}\n\nGerencie seus alertas: {link}\n\n_{AVISO}_"


def compor_codigo_whatsapp(codigo: str) -> str:
    return (
        f"Seu código do analisebolsa é *{codigo}*. Ele vale por 10 minutos.\n\n"
        "Se não foi você que pediu, ignore esta mensagem."
    )
