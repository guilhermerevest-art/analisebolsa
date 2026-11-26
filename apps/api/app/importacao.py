"""Importação de operações pelo extrato de negociação da B3 (Fase 5, etapa 2).

A prévia diz o que vai entrar; a importação relê o mesmo arquivo e grava só as linhas novas,
numa transação: se alguma venda passar da posição, nada entra.
"""

from collections import Counter
from datetime import date
from decimal import ROUND_HALF_EVEN, Decimal

from sqlalchemy import Connection, text

from app import carteira as c
from app.erros import Problema
from dominio.carteira import VendaAcimaDaPosicao, consolidar
from dominio.importacao_b3 import LinhaB3, PlanilhaInvalida, ler_negociacao

Q4 = Decimal("0.0001")
TAMANHO_MAXIMO = 2 * 1024 * 1024


def _chave(data: date, ticker: str, tipo: str, quantidade: Decimal, preco: Decimal) -> tuple:
    q = lambda v: Decimal(v).quantize(Q4, ROUND_HALF_EVEN)  # noqa: E731
    return (data, ticker, tipo, q(quantidade), q(preco))


def _ler(conteudo: bytes) -> list[LinhaB3]:
    if len(conteudo) > TAMANHO_MAXIMO:
        raise Problema(413, "o arquivo passa de 2 MB")
    try:
        return ler_negociacao(conteudo)
    except PlanilhaInvalida as e:
        raise Problema(422, str(e)) from e


def analisar(conn: Connection, user_id: str, carteira_id: int, conteudo: bytes, hoje: date) -> dict:
    c.obter(conn, user_id, carteira_id)
    linhas = _ler(conteudo)
    tickers = sorted({ln.ticker for ln in linhas if ln.ticker and ln.erro is None})
    conhecidos = set(
        conn.execute(
            text("SELECT ticker FROM ativos WHERE ticker = ANY(:t)"), {"t": tickers}
        ).scalars()
    )
    existentes = Counter(
        _chave(o.data, o.ticker, o.tipo, o.quantidade, o.preco)
        for o in c._operacoes_dominio(conn, carteira_id)
    )

    saida = []
    for ln in linhas:
        situacao, motivo = "nova", None
        if ln.erro:
            situacao, motivo = "ignorada", ln.erro
        elif ln.data > hoje:
            situacao, motivo = "ignorada", "data no futuro"
        elif ln.ticker not in conhecidos:
            situacao, motivo = "ignorada", f"{ln.ticker} não está no catálogo do site"
        else:
            chave = _chave(ln.data, ln.ticker, ln.tipo, ln.quantidade, ln.preco)
            if existentes[chave] > 0:  # cada operação igual já lançada "consome" uma linha
                existentes[chave] -= 1
                situacao, motivo = "duplicada", "já está na carteira"
        saida.append(
            {
                "linha": ln.linha,
                "data": ln.data,
                "tipo": ln.tipo,
                "ticker": ln.ticker,
                "quantidade": ln.quantidade,
                "preco": ln.preco.quantize(Q4, ROUND_HALF_EVEN) if ln.preco else None,
                "situacao": situacao,
                "motivo": motivo,
            }
        )
    contagem = Counter(s["situacao"] for s in saida)
    return {
        "linhas": saida,
        "novas": contagem["nova"],
        "duplicadas": contagem["duplicada"],
        "ignoradas": contagem["ignorada"],
    }


def importar(conn: Connection, user_id: str, carteira_id: int, conteudo: bytes, hoje: date) -> dict:
    previa = analisar(conn, user_id, carteira_id, conteudo, hoje)
    novas = [ln for ln in previa["linhas"] if ln["situacao"] == "nova"]
    if not novas:
        raise Problema(422, "nenhuma operação nova para importar")
    carteira = c.obter(conn, user_id, carteira_id)
    if carteira["operacoes"] + len(novas) > c.LIMITE_OPERACOES:
        raise Problema(409, f"cada carteira aceita até {c.LIMITE_OPERACOES} operações")
    ids = dict(
        conn.execute(
            text("SELECT ticker, ativo_id FROM ativos WHERE ticker = ANY(:t)"),
            {"t": sorted({ln["ticker"] for ln in novas})},
        ).all()
    )
    conn.execute(
        text(
            """
            INSERT INTO operacoes (carteira_id, ativo_id, tipo, data, quantidade, preco, custos)
            VALUES (:c, :a, :tipo, :data, :quantidade, :preco, 0)
            """
        ),
        [
            {
                "c": carteira_id,
                "a": ids[ln["ticker"]],
                "tipo": ln["tipo"],
                "data": ln["data"],
                "quantidade": ln["quantidade"],
                "preco": ln["preco"],
            }
            for ln in novas
        ],
    )
    try:
        consolidar(c._operacoes_dominio(conn, carteira_id))
    except VendaAcimaDaPosicao as e:
        conn.rollback()
        raise Problema(
            422,
            f"{e}. Nada foi importado: confira se a planilha começa na primeira compra desse "
            "ativo, ou lance antes a posição que você já tinha",
        ) from e
    return {
        "importadas": len(novas),
        "duplicadas": previa["duplicadas"],
        "ignoradas": previa["ignoradas"],
    }
