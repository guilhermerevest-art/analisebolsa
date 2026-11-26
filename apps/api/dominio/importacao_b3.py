"""Leitura do extrato de negociação da B3 (Área do Investidor → Extratos → Negociação).

Puro: recebe os bytes do .xlsx e devolve as linhas interpretadas, sem banco. O cabeçalho é
localizado pelo nome das colunas (sem depender da posição), e cada linha que não vira
operação diz o motivo.

Colunas usadas: Data do Negócio, Tipo de Movimentação, Mercado, Código de Negociação,
Quantidade e Preço. Mercado fracionário vira o mesmo ticker do lote padrão (PETR4F → PETR4).
Opções, termo e futuros ficam de fora.
"""

import io
import re
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from itertools import islice

MAX_LINHAS = 5000

COLUNAS = {
    "data": ("data do negocio", "data"),
    "tipo": ("tipo de movimentacao", "movimentacao", "compra/venda", "c/v"),
    "mercado": ("mercado",),
    "ticker": ("codigo de negociacao", "codigo", "ticker", "ativo"),
    "quantidade": ("quantidade", "qtd", "qtde"),
    "preco": ("preco", "preco unitario", "preco (r$)"),
}
OBRIGATORIAS = ("data", "tipo", "ticker", "quantidade", "preco")
MERCADOS_ACEITOS = ("mercado a vista", "mercado fracionario", "vista", "fracionario")


class PlanilhaInvalida(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class LinhaB3:
    linha: int  # número da linha na planilha, para o usuário achar
    data: date | None
    tipo: str | None  # "compra" | "venda"
    ticker: str | None
    quantidade: Decimal | None
    preco: Decimal | None
    erro: str | None = None  # motivo de não virar operação


def _norm(v: object) -> str:
    t = unicodedata.normalize("NFKD", str(v or "")).encode("ascii", "ignore").decode()
    return " ".join(t.lower().split())


def _data(v: object) -> date | None:
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    m = re.fullmatch(r"(\d{2})/(\d{2})/(\d{4})", str(v or "").strip())
    if not m:
        return None
    try:
        return date(int(m[3]), int(m[2]), int(m[1]))
    except ValueError:
        return None


def _decimal(v: object) -> Decimal | None:
    if isinstance(v, bool) or v is None:
        return None
    if isinstance(v, int | float):
        return Decimal(str(v))
    t = re.sub(r"[^\d,.\-]", "", str(v))
    if not t or t == "-":
        return None
    if "," in t:  # formato brasileiro: 1.234,56
        t = t.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"-?\d{1,3}(\.\d{3})+", t):  # só milhar: 1.000 é mil, não um
        t = t.replace(".", "")
    try:
        return Decimal(t)
    except InvalidOperation:
        return None


def normalizar_ticker(v: object) -> str | None:
    t = str(v or "").strip().upper()
    # Raiz de 4 caracteres terminada em letra (PETR, B3SA) e 1 ou 2 dígitos; o fracionário
    # tem um F no fim (PETR4F).
    m = re.fullmatch(r"([A-Z0-9]{3}[A-Z]\d{1,2})F?", t)
    return m[1] if m else None


def _tipo(v: object) -> str | None:
    t = _norm(v)
    if t in ("compra", "c"):
        return "compra"
    if t in ("venda", "v"):
        return "venda"
    return None


def _cabecalho(linhas: list[tuple]) -> tuple[int, dict[str, int]]:
    for i, linha in enumerate(linhas[:20]):
        nomes = [_norm(c) for c in linha]
        mapa: dict[str, int] = {}
        for campo, alternativas in COLUNAS.items():
            for j, nome in enumerate(nomes):
                if nome in alternativas and j not in mapa.values():
                    mapa[campo] = j
                    break
        if all(c in mapa for c in OBRIGATORIAS):
            return i, mapa
    raise PlanilhaInvalida(
        "não achei as colunas do extrato de negociação da B3 (Data do Negócio, Tipo de "
        "Movimentação, Código de Negociação, Quantidade e Preço)"
    )


def ler_negociacao(conteudo: bytes) -> list[LinhaB3]:
    from openpyxl import load_workbook

    try:
        livro = load_workbook(io.BytesIO(conteudo), read_only=True, data_only=True)
    except Exception as e:
        raise PlanilhaInvalida("o arquivo não é uma planilha .xlsx válida") from e
    try:
        planilha = livro.worksheets[0]
        # Leitura preguiçosa com teto: um .xlsx pequeno pode expandir para milhões de linhas.
        teto = MAX_LINHAS + 20
        linhas = [
            tuple(r) for r in islice(planilha.iter_rows(values_only=True, max_col=30), teto + 1)
        ]
    finally:
        livro.close()

    if len(linhas) > teto:
        raise PlanilhaInvalida(f"a planilha passa de {MAX_LINHAS} linhas")
    inicio, col = _cabecalho(linhas)
    saida: list[LinhaB3] = []
    for n, linha in enumerate(linhas[inicio + 1 :], start=inicio + 2):
        if not any(c not in (None, "") for c in linha):
            continue

        def valor(campo: str, linha: tuple = linha) -> object:
            j = col.get(campo)
            return linha[j] if j is not None and j < len(linha) else None

        bruto = str(valor("ticker") or "").strip().upper()
        campos = {
            "data": _data(valor("data")),
            "tipo": _tipo(valor("tipo")),
            "ticker": normalizar_ticker(valor("ticker")),
            "quantidade": _decimal(valor("quantidade")),
            "preco": _decimal(valor("preco")),
        }
        mercado = _norm(valor("mercado"))
        erro = None
        if mercado and mercado not in MERCADOS_ACEITOS:
            erro = f"mercado {valor('mercado')} não é importado (só à vista e fracionário)"
        elif campos["data"] is None:
            erro = "data inválida"
        elif campos["tipo"] is None:
            erro = "tipo de movimentação inválido (esperado Compra ou Venda)"
        elif campos["ticker"] is None:
            erro = f"código de negociação inválido: {bruto or 'vazio'}"
        elif campos["quantidade"] is None or campos["quantidade"] <= 0:
            erro = "quantidade inválida"
        elif campos["preco"] is None or campos["preco"] <= 0:
            erro = "preço inválido"
        if campos["ticker"] is None and bruto:
            campos["ticker"] = bruto[:12]
        saida.append(LinhaB3(n, **campos, erro=erro))
    if not saida:
        raise PlanilhaInvalida("a planilha não tem operações")
    return saida
