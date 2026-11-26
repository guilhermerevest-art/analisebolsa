"""Carteiras e operações do usuário (Fase 3, etapa 2). Toda consulta filtra pelo dono."""

from collections import defaultdict
from datetime import date
from decimal import Decimal

from sqlalchemy import Connection, RowMapping, text

from app.erros import Problema
from app.usuario import exigir_usuario_existente
from dominio.carteira import Consolidacao, Operacao, VendaAcimaDaPosicao, alocacao, consolidar
from dominio.imposto import CODIGO_DARF, apurar
from dominio.modelos import Provento
from dominio.rentabilidade import reduzir, serie_rentabilidade

LIMITE_CARTEIRAS = 5
LIMITE_OPERACOES = 2000
CENTAVO = Decimal("0.01")
QUATRO_CASAS = Decimal("0.0001")
NOMES_TIPO = {"acao": "Ações", "fii": "FIIs", "etf": "ETFs", "bdr": "BDRs"}


# Carteiras


def listar(conn: Connection, user_id: str) -> list[RowMapping]:
    return list(
        conn.execute(
            text(
                """
                SELECT c.carteira_id AS id, c.nome, c.criado_em, count(o.operacao_id) AS operacoes
                FROM carteiras c LEFT JOIN operacoes o USING (carteira_id)
                WHERE c.user_id = :u
                GROUP BY c.carteira_id ORDER BY c.criado_em, c.carteira_id
                """
            ),
            {"u": user_id},
        ).mappings()
    )


def obter(conn: Connection, user_id: str, carteira_id: int) -> RowMapping:
    linha = (
        conn.execute(
            text(
                """
                SELECT c.carteira_id AS id, c.nome, c.criado_em, count(o.operacao_id) AS operacoes
                FROM carteiras c LEFT JOIN operacoes o USING (carteira_id)
                WHERE c.user_id = :u AND c.carteira_id = :c
                GROUP BY c.carteira_id
                """
            ),
            {"u": user_id, "c": carteira_id},
        )
        .mappings()
        .one_or_none()
    )
    if linha is None:  # carteira de outro usuário também é 404
        raise Problema(404, "carteira não encontrada")
    return linha


def criar(conn: Connection, user_id: str, nome: str) -> RowMapping:
    exigir_usuario_existente(conn, user_id)
    total = conn.execute(
        text("SELECT count(*) FROM carteiras WHERE user_id = :u"), {"u": user_id}
    ).scalar_one()
    if total >= LIMITE_CARTEIRAS:
        raise Problema(409, f"cada conta pode ter até {LIMITE_CARTEIRAS} carteiras")
    novo = conn.execute(
        text("INSERT INTO carteiras (user_id, nome) VALUES (:u, :n) RETURNING carteira_id"),
        {"u": user_id, "n": nome},
    ).scalar_one()
    return obter(conn, user_id, novo)


def renomear(conn: Connection, user_id: str, carteira_id: int, nome: str) -> RowMapping:
    obter(conn, user_id, carteira_id)
    conn.execute(
        text("UPDATE carteiras SET nome = :n WHERE carteira_id = :c"),
        {"n": nome, "c": carteira_id},
    )
    return obter(conn, user_id, carteira_id)


def excluir(conn: Connection, user_id: str, carteira_id: int) -> None:
    obter(conn, user_id, carteira_id)
    conn.execute(text("DELETE FROM carteiras WHERE carteira_id = :c"), {"c": carteira_id})


# Operações

SQL_OPERACOES = """
SELECT o.operacao_id AS id, a.ticker, a.nome, o.tipo, o.data, o.quantidade, o.preco, o.custos
FROM operacoes o JOIN ativos a USING (ativo_id)
WHERE o.carteira_id = :c
"""


def operacoes(conn: Connection, carteira_id: int) -> list[RowMapping]:
    return list(
        conn.execute(
            text(SQL_OPERACOES + " ORDER BY o.data DESC, o.operacao_id DESC"), {"c": carteira_id}
        ).mappings()
    )


def _ativo_id(conn: Connection, ticker: str) -> int:
    ativo_id = conn.execute(
        text("SELECT ativo_id FROM ativos WHERE ticker = :t"), {"t": ticker}
    ).scalar_one_or_none()
    if ativo_id is None:
        raise Problema(422, f"ativo {ticker} não encontrado")
    return ativo_id


def _validar_posicoes(conn: Connection, carteira_id: int) -> None:
    """Depois de qualquer mudança, nenhuma venda pode passar da posição na sua data."""
    try:
        consolidar(_operacoes_dominio(conn, carteira_id))
    except VendaAcimaDaPosicao as e:
        raise Problema(422, str(e)) from e


def lancar(conn: Connection, user_id: str, carteira_id: int, dados: dict) -> RowMapping:
    carteira = obter(conn, user_id, carteira_id)
    if carteira["operacoes"] >= LIMITE_OPERACOES:
        raise Problema(409, f"cada carteira aceita até {LIMITE_OPERACOES} operações")
    novo = conn.execute(
        text(
            """
            INSERT INTO operacoes (carteira_id, ativo_id, tipo, data, quantidade, preco, custos)
            VALUES (:c, :a, :tipo, :data, :quantidade, :preco, :custos)
            RETURNING operacao_id
            """
        ),
        dados | {"c": carteira_id, "a": _ativo_id(conn, dados["ticker"])},
    ).scalar_one()
    _validar_posicoes(conn, carteira_id)
    return _operacao(conn, carteira_id, novo)


def editar(conn: Connection, user_id: str, carteira_id: int, op_id: int, dados: dict) -> RowMapping:
    obter(conn, user_id, carteira_id)
    _operacao(conn, carteira_id, op_id)
    conn.execute(
        text(
            """
            UPDATE operacoes SET ativo_id = :a, tipo = :tipo, data = :data,
              quantidade = :quantidade, preco = :preco, custos = :custos
            WHERE operacao_id = :o AND carteira_id = :c
            """
        ),
        dados | {"c": carteira_id, "o": op_id, "a": _ativo_id(conn, dados["ticker"])},
    )
    _validar_posicoes(conn, carteira_id)
    return _operacao(conn, carteira_id, op_id)


def remover(conn: Connection, user_id: str, carteira_id: int, op_id: int) -> None:
    obter(conn, user_id, carteira_id)
    _operacao(conn, carteira_id, op_id)
    conn.execute(
        text("DELETE FROM operacoes WHERE operacao_id = :o AND carteira_id = :c"),
        {"o": op_id, "c": carteira_id},
    )
    _validar_posicoes(conn, carteira_id)


def _operacao(conn: Connection, carteira_id: int, op_id: int) -> RowMapping:
    linha = (
        conn.execute(
            text(SQL_OPERACOES + " AND o.operacao_id = :o"), {"c": carteira_id, "o": op_id}
        )
        .mappings()
        .one_or_none()
    )
    if linha is None:
        raise Problema(404, "operação não encontrada")
    return linha


def _operacoes_dominio(conn: Connection, carteira_id: int) -> list[Operacao]:
    return [
        Operacao(
            r["id"], r["ticker"], r["tipo"], r["data"], r["quantidade"], r["preco"], r["custos"]
        )
        for r in conn.execute(text(SQL_OPERACOES), {"c": carteira_id}).mappings()
    ]


# Resumo


def _proventos_e_eventos(conn: Connection, tickers: list[str]) -> dict[str, list[Provento]]:
    saida: dict[str, list[Provento]] = defaultdict(list)
    if not tickers:
        return saida
    linhas = conn.execute(
        text(
            """
            SELECT a.ticker, p.tipo, p.data_com, p.valor, p.data_pagamento
            FROM proventos p JOIN ativos a USING (ativo_id)
            WHERE a.ticker = ANY(:t) ORDER BY p.data_com
            """
        ),
        {"t": tickers},
    )
    for ticker, tipo, data_com, valor, pagamento in linhas:
        saida[ticker].append(Provento(tipo, data_com, valor, pagamento))
    return saida


def _cadastro_e_precos(conn: Connection, tickers: list[str]) -> dict[str, RowMapping]:
    if not tickers:
        return {}
    linhas = conn.execute(
        text(
            """
            SELECT a.ticker, a.nome, a.tipo, a.setor, u.data, u.fechamento
            FROM ativos a
            LEFT JOIN LATERAL (
              SELECT data, fechamento FROM cotacoes_diarias c
              WHERE c.ativo_id = a.ativo_id ORDER BY data DESC LIMIT 1
            ) u ON true
            WHERE a.ticker = ANY(:t)
            """
        ),
        {"t": tickers},
    ).mappings()
    return {r["ticker"]: r for r in linhas}


def _r(v: Decimal | None, casas: Decimal = CENTAVO) -> Decimal | None:
    return None if v is None else v.quantize(casas)


def resumo(conn: Connection, user_id: str, carteira_id: int, hoje: date) -> dict:
    carteira = obter(conn, user_id, carteira_id)
    ops = _operacoes_dominio(conn, carteira_id)
    tickers = sorted({o.ticker for o in ops})
    cons: Consolidacao = consolidar(ops, _proventos_e_eventos(conn, tickers), ate=hoje)
    cadastro = _cadastro_e_precos(conn, tickers)

    posicoes, por_ativo, por_setor, por_tipo = [], {}, defaultdict(Decimal), defaultdict(Decimal)
    patrimonio = custo = custo_cotado = Decimal(0)
    for p in cons.abertas:
        info = cadastro[p.ticker]
        preco = info["fechamento"]
        valor = (p.quantidade * preco) if preco is not None else None
        posicoes.append(
            {
                "ticker": p.ticker,
                "nome": info["nome"],
                "tipo": info["tipo"],
                "setor": info["setor"],
                "quantidade": p.quantidade,
                "preco_medio": _r(p.preco_medio, QUATRO_CASAS),
                "custo": _r(p.custo),
                "preco_atual": preco,
                "data_preco": info["data"],
                "valor_atual": _r(valor),
                "resultado": _r(valor - p.custo) if valor is not None else None,
                "variacao": float((valor / p.custo - 1) * 100) if valor and p.custo else None,
                "proventos": _r(p.proventos),
            }
        )
        custo += p.custo
        if valor is not None:
            patrimonio += valor
            custo_cotado += p.custo
            por_ativo[p.ticker] = valor
            por_setor[info["setor"] or "Sem setor"] += valor
            por_tipo[NOMES_TIPO[info["tipo"]]] += valor

    def fatias(valores: dict) -> list[dict]:
        return [
            {"chave": f.chave, "valor": _r(f.valor), "percentual": f.percentual}
            for f in alocacao(valores)
        ]

    realizado = sum((p.resultado_realizado for p in cons.posicoes.values()), Decimal(0))
    proventos_total = sum((p.total for p in cons.proventos), Decimal(0))
    nao_realizado = patrimonio - custo_cotado  # ativo sem cotação fica de fora
    return {
        "carteira": carteira,
        "totais": {
            "patrimonio": _r(patrimonio),
            "custo": _r(custo),
            "resultado_nao_realizado": _r(nao_realizado),
            "resultado_realizado": _r(realizado),
            "proventos": _r(proventos_total),
            "resultado_total": _r(nao_realizado + realizado + proventos_total),
        },
        "posicoes": posicoes,
        "alocacao": {
            "ativo": fatias(por_ativo),
            "setor": fatias(dict(por_setor)),
            "tipo": fatias(dict(por_tipo)),
        },
        "proventos": [
            {
                "ticker": r.ticker,
                "tipo": r.tipo,
                "data_com": r.data_com,
                "data_pagamento": r.data_pagamento,
                "valor_unitario": r.valor_unitario,
                "quantidade": r.quantidade,
                "total": r.total,
            }
            for r in reversed(cons.proventos)
        ],
    }


# Rentabilidade (etapa 3)


def _precos(conn: Connection, tickers: list[str], inicio: date) -> dict[str, dict[date, Decimal]]:
    saida: dict[str, dict[date, Decimal]] = defaultdict(dict)
    linhas = conn.execute(
        text(
            """
            SELECT a.ticker, c.data, c.fechamento
            FROM cotacoes_diarias c JOIN ativos a USING (ativo_id)
            WHERE a.ticker = ANY(:t) AND c.data >= :i
            """
        ),
        {"t": tickers, "i": inicio},
    )
    for ticker, d, fechamento in linhas:
        saida[ticker][d] = fechamento
    return saida


def _indice(conn: Connection, serie: str, inicio: date) -> dict[date, float]:
    return dict(
        conn.execute(
            text("SELECT data, valor FROM indices WHERE serie = :s AND data >= :i"),
            {"s": serie, "i": inicio},
        ).all()
    )


def rentabilidade(conn: Connection, user_id: str, carteira_id: int) -> dict:
    obter(conn, user_id, carteira_id)
    ops = _operacoes_dominio(conn, carteira_id)
    if not ops:
        return {"inicio": None, "pontos": [], "acumulado": None}
    inicio = min(o.data for o in ops)
    tickers = sorted({o.ticker for o in ops})
    pontos = serie_rentabilidade(
        ops,
        _proventos_e_eventos(conn, tickers),
        _precos(conn, tickers, inicio),
        cdi=_indice(conn, "cdi", inicio),
        ibov=_indice(conn, "ibov", inicio),
    )
    ultimo = pontos[-1]
    return {
        "inicio": inicio,
        "pontos": reduzir(pontos),
        "acumulado": {
            "data": ultimo.data,
            "carteira": ultimo.carteira,
            "cdi": ultimo.cdi,
            "ibov": ultimo.ibov,
        },
    }


# Imposto de renda (Fase 5, etapa 3)

AVISO_IMPOSTO = (
    "Conta feita com as operações lançadas, para conferência. Não substitui a declaração nem "
    "um contador. O IRRF é uma estimativa (confira nas notas de corretagem), day trade e "
    "ETFs de renda fixa têm outras regras."
)


def imposto(conn: Connection, user_id: str, carteira_id: int) -> dict:
    obter(conn, user_id, carteira_id)
    ops = _operacoes_dominio(conn, carteira_id)
    tickers = sorted({o.ticker for o in ops})
    eventos = {
        t: [p for p in lista if p.societario]
        for t, lista in _proventos_e_eventos(conn, tickers).items()
    }
    consolidado = consolidar(ops, eventos)
    tipos = {t: r["tipo"] for t, r in _cadastro_e_precos(conn, tickers).items()}
    compras: dict[str, set[date]] = defaultdict(set)
    for o in ops:
        if o.tipo == "compra":
            compras[o.ticker].add(o.data)
    ap = apurar(consolidado.vendas, tipos, compras)

    meses = [
        {
            "mes": m.mes,
            "vendas_acoes": m.vendas_acoes,
            "vendas_total": m.vendas_total,
            "isento_acoes": m.isento_acoes,
            "resultado_acoes": m.resultado_acoes,
            "ganho_isento": m.ganho_isento,
            "resultado_etf_bdr": m.resultado_etf_bdr,
            "resultado_fii": m.resultado_fii,
            "compensado": m.compensado_comum + m.compensado_fii,
            "base_comum": m.base_comum,
            "base_fii": m.base_fii,
            "imposto_devido": m.imposto_devido,
            "irrf": m.irrf,
            "irrf_usado": m.irrf_usado,
            "acumulado_anterior": m.acumulado_anterior,
            "darf": m.darf,
            "vencimento": m.vencimento,
            "fica_para_depois": m.fica_para_depois,
            "prejuizo_comum": m.prejuizo_comum,
            "prejuizo_fii": m.prejuizo_fii,
        }
        for m in reversed(ap.meses)
    ]
    anos: dict[int, dict] = {}
    for m in ap.meses:
        a = anos.setdefault(
            m.mes.year,
            {
                "ano": m.mes.year,
                "ganho_isento": Decimal(0),
                "darf": Decimal(0),
                "vendas": Decimal(0),
            },
        )
        a["ganho_isento"] += m.ganho_isento
        a["darf"] += m.darf
        a["vendas"] += m.vendas_total
    return {
        "meses": meses,
        "anos": sorted(anos.values(), key=lambda a: -a["ano"]),
        "prejuizo_comum": ap.prejuizo_comum,
        "prejuizo_fii": ap.prejuizo_fii,
        "pendente": ap.pendente,
        "saldo_irrf": ap.saldo_irrf,
        "codigo_darf": CODIGO_DARF,
        "day_trade": [{"ticker": t, "data": d} for t, d in ap.day_trade],
        "aviso": AVISO_IMPOSTO,
    }
