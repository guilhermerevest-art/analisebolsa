"""Números em português do Brasil para os textos da análise (insights e cenários)."""


def num(v: float, casas: int = 2) -> str:
    texto = f"{v:,.{casas}f}"
    return texto.replace(",", "_").replace(".", ",").replace("_", ".")


def brl(v: float) -> str:
    return f"R$ {num(v, 2)}"


def pct(v: float, casas: int = 1) -> str:
    return f"{num(v, casas)}%"


def quando(pregoes_atras: int) -> str:
    if pregoes_atras == 0:
        return "no último pregão"
    if pregoes_atras == 1:
        return "há 1 pregão"
    return f"há {pregoes_atras} pregões"
