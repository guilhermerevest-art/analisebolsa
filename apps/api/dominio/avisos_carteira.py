"""Avisos sobre a carteira: textos e chaves (a chave impede o mesmo aviso duas vezes).

Os avisos informam datas e valores; não sugerem comprar, vender nem resgatar.
"""

from dataclasses import dataclass
from datetime import date

from dominio.formato import num

TIPOS = ("proventos", "data_com", "darf", "vencimentos")
NOMES_PROVENTO = {"dividendo": "dividendos", "jcp": "JCP", "rendimento": "rendimentos"}
DIAS_DATA_COM = 5
DIAS_DARF = 7
DIAS_VENCIMENTO = 7
AVISO = "Conteúdo educacional, não é recomendação de investimento."


@dataclass(frozen=True, slots=True)
class Aviso:
    tipo: str
    chave: str
    data: date
    texto: str
    url: str


def _d(d: date) -> str:
    return d.strftime("%d/%m/%Y")


def _r(v: float) -> str:
    return f"R$ {num(float(v), 2)}"


def provento_pago(
    carteira_id: int,
    carteira: str,
    ticker: str,
    tipo: str,
    data_com: date,
    pagamento: date,
    total: float,
) -> Aviso:
    return Aviso(
        "proventos",
        f"prov:{carteira_id}:{ticker}:{tipo}:{data_com}",
        pagamento,
        f"{ticker} paga {_r(total)} de {NOMES_PROVENTO.get(tipo, tipo)} em {_d(pagamento)} "
        f"(carteira {carteira}).",
        f"/carteira?c={carteira_id}",
    )


def data_com(ticker: str, tipo: str, data: date, valor: float, pagamento: date | None) -> Aviso:
    quando = f", pagos em {_d(pagamento)}" if pagamento else ""
    return Aviso(
        "data_com",
        f"com:{ticker}:{tipo}:{data}",
        data,
        f"{ticker} tem data com em {_d(data)}: quem tiver o ativo no fim desse dia recebe "
        f"R$ {num(float(valor), 4).rstrip('0').rstrip(',')} por cota de "
        f"{NOMES_PROVENTO.get(tipo, tipo)}{quando}.",
        f"/ativo/{ticker}",
    )


def darf(carteira_id: int, carteira: str, mes: date, valor: float, vencimento: date) -> Aviso:
    return Aviso(
        "darf",
        f"darf:{carteira_id}:{mes:%Y-%m}",
        vencimento,
        f"O DARF de {_r(valor)} da carteira {carteira} (ganhos de {mes:%m/%Y}) vence em "
        f"{_d(vencimento)}. Código 6015.",
        f"/carteira/imposto?c={carteira_id}",
    )


def vencimento(
    carteira_id: int, carteira: str, investimento_id: int, nome: str, data: date
) -> Aviso:
    return Aviso(
        "vencimentos",
        f"venc:{investimento_id}:{data}",
        data,
        f"{nome} vence em {_d(data)} (carteira {carteira}).",
        f"/carteira?c={carteira_id}#renda-fixa",
    )


def compor_push(avisos: list[Aviso]) -> dict[str, str]:
    n = len(avisos)
    titulo = "Aviso da carteira" if n == 1 else f"{n} avisos da carteira"
    corpo = avisos[0].texto + (f" E mais {n - 1}." if n > 1 else "")
    return {"titulo": titulo, "corpo": corpo, "url": avisos[0].url if n == 1 else "/carteira"}


def compor_whatsapp(avisos: list[Aviso], link: str) -> str:
    itens = "\n".join(f"• {a.texto}" for a in avisos)
    cabecalho = (
        "Aviso da sua carteira no analisebolsa:"
        if len(avisos) == 1
        else (f"{len(avisos)} avisos da sua carteira no analisebolsa:")
    )
    return f"{cabecalho}\n\n{itens}\n\nVer a carteira: {link}\n\n_{AVISO}_"
