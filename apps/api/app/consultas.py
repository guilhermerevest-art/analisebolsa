"""Consultas SQL da API (SQLAlchemy core, somente leitura)."""

from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import Connection, RowMapping, text

from app.erros import Problema

TIPOS_DINHEIRO = ("dividendo", "jcp", "rendimento")


def ativo_por_ticker(conn: Connection, ticker: str) -> RowMapping:
    linha = (
        conn.execute(
            text(
                "SELECT ativo_id, ticker, nome, tipo, setor, segmento, logo_url "
                "FROM ativos WHERE ticker = :t"
            ),
            {"t": ticker},
        )
        .mappings()
        .first()
    )
    if linha is None:
        raise Problema(404, f"ativo {ticker} não encontrado")
    return linha


def _escapar_like(s: str) -> str:
    return s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def buscar_ativos(
    conn: Connection, busca: str | None, tipo: str | None, pagina: int, limite: int
) -> tuple[list[RowMapping], int]:
    termo = (busca or "").strip() or None
    params = {
        "b": termo,
        "exato": termo.upper() if termo else None,
        "prefixo": _escapar_like(termo.upper()) + "%" if termo else None,
        "contem": "%" + _escapar_like(termo) + "%" if termo else None,
        "tipo": tipo,
        "limite": limite,
        "offset": (pagina - 1) * limite,
    }
    linhas = (
        conn.execute(
            text(
                """
                SELECT ticker, nome, tipo, setor, segmento, logo_url, count(*) OVER () AS total
                FROM ativos
                WHERE ativo
                  AND (CAST(:tipo AS text) IS NULL OR tipo = :tipo)
                  AND (CAST(:b AS text) IS NULL
                       OR ticker LIKE :prefixo
                       OR nome ILIKE :contem
                       OR nome % CAST(:b AS text))
                ORDER BY (ticker = :exato) DESC NULLS LAST,
                         (ticker LIKE :prefixo) DESC NULLS LAST,
                         similarity(nome, CAST(:b AS text)) DESC NULLS LAST,
                         ticker
                LIMIT :limite OFFSET :offset
                """
            ),
            params,
        )
        .mappings()
        .all()
    )
    total = linhas[0]["total"] if linhas else 0
    if not linhas and pagina > 1:
        total = conn.execute(
            text(
                """
                SELECT count(*) FROM ativos WHERE ativo
                  AND (CAST(:tipo AS text) IS NULL OR tipo = :tipo)
                  AND (CAST(:b AS text) IS NULL OR ticker LIKE :prefixo
                       OR nome ILIKE :contem OR nome % CAST(:b AS text))
                """
            ),
            params,
        ).scalar_one()
    return list(linhas), total


def _pct(atual: Decimal | None, base: Decimal | None) -> float | None:
    if atual is None or not base:
        return None
    return round(float((atual / base - 1) * 100), 2)


def ultima_e_variacoes(conn: Connection, ativo_id: int) -> tuple[RowMapping | None, dict]:
    ultimas = (
        conn.execute(
            text(
                "SELECT data, abertura, maxima, minima, fechamento, fechamento_ajustado, volume "
                "FROM cotacoes_diarias WHERE ativo_id = :a ORDER BY data DESC LIMIT 2"
            ),
            {"a": ativo_id},
        )
        .mappings()
        .all()
    )
    if not ultimas:
        return None, {"dia": None, "doze_meses": None, "ano": None}
    ultima = ultimas[0]

    def ajustado_ate(limite: date) -> Decimal | None:
        return conn.execute(
            text(
                "SELECT fechamento_ajustado FROM cotacoes_diarias "
                "WHERE ativo_id = :a AND data <= :d ORDER BY data DESC LIMIT 1"
            ),
            {"a": ativo_id, "d": limite},
        ).scalar_one_or_none()

    um_ano = ultima["data"] - timedelta(days=365)
    fim_ano_anterior = date(ultima["data"].year - 1, 12, 31)
    variacoes = {
        "dia": _pct(ultima["fechamento"], ultimas[1]["fechamento"]) if len(ultimas) > 1 else None,
        "doze_meses": _pct(ultima["fechamento_ajustado"], ajustado_ate(um_ano)),
        "ano": _pct(ultima["fechamento_ajustado"], ajustado_ate(fim_ano_anterior)),
    }
    return ultima, variacoes


UNIDADES = {"1w": "week", "1M": "month"}


def cotacoes(
    conn: Connection, ativo_id: int, inicio: date, fim: date, periodo: str
) -> list[RowMapping]:
    params = {"a": ativo_id, "i": inicio, "f": fim}
    if periodo == "1d":
        sql = """
            SELECT data, abertura, maxima, minima, fechamento, fechamento_ajustado, volume
            FROM cotacoes_diarias
            WHERE ativo_id = :a AND data BETWEEN :i AND :f
            ORDER BY data
        """
    else:
        params["u"] = UNIDADES[periodo]
        sql = """
            SELECT min(data) AS data,
                   (array_agg(abertura ORDER BY data))[1] AS abertura,
                   max(maxima) AS maxima,
                   min(minima) AS minima,
                   (array_agg(fechamento ORDER BY data DESC))[1] AS fechamento,
                   (array_agg(fechamento_ajustado ORDER BY data DESC))[1] AS fechamento_ajustado,
                   sum(volume)::bigint AS volume
            FROM cotacoes_diarias
            WHERE ativo_id = :a AND data BETWEEN :i AND :f
            GROUP BY date_trunc(:u, data)
            ORDER BY 1
        """
    return list(conn.execute(text(sql), params).mappings())


def indicadores(conn: Connection, ativo_id: int, inicio: date, fim: date) -> list[RowMapping]:
    return list(
        conn.execute(
            text(
                """
                SELECT data, mm20, mm50, mm200, mme9, rsi14, macd, macd_sinal, macd_hist,
                       bb_superior, bb_inferior, atr14, vol_media20
                FROM indicadores_diarios
                WHERE ativo_id = :a AND data BETWEEN :i AND :f
                ORDER BY data
                """
            ),
            {"a": ativo_id, "i": inicio, "f": fim},
        ).mappings()
    )


def fundamentos(conn: Connection, ativo_id: int) -> list[RowMapping]:
    return list(
        conn.execute(
            text(
                """
                SELECT data_referencia, pl, pvp, dy_12m, roe, margem_liquida, div_liq_ebitda,
                       vpa, lpa, valor_mercado, extras
                FROM fundamentos WHERE ativo_id = :a ORDER BY data_referencia DESC
                """
            ),
            {"a": ativo_id},
        ).mappings()
    )


def proventos(conn: Connection, ativo_id: int) -> tuple[list[RowMapping], list[dict]]:
    itens = list(
        conn.execute(
            text(
                "SELECT tipo, data_com, data_pagamento, valor FROM proventos "
                "WHERE ativo_id = :a ORDER BY data_com DESC, tipo"
            ),
            {"a": ativo_id},
        ).mappings()
    )
    por_ano = conn.execute(
        text(
            """
            WITH soma AS (
              SELECT extract(year FROM data_com)::int AS ano, sum(valor) AS total
              FROM proventos WHERE ativo_id = :a AND tipo IN ('dividendo','jcp','rendimento')
              GROUP BY 1
            ), preco AS (
              SELECT DISTINCT ON (extract(year FROM data)::int)
                     extract(year FROM data)::int AS ano, fechamento
              FROM cotacoes_diarias WHERE ativo_id = :a
              ORDER BY extract(year FROM data)::int, data DESC
            )
            SELECT s.ano, s.total, p.fechamento
            FROM soma s LEFT JOIN preco p USING (ano)
            ORDER BY s.ano DESC
            """
        ),
        {"a": ativo_id},
    ).all()
    dy = [
        {
            "ano": ano,
            "total": total,
            "dy": round(float(total / preco * 100), 2) if preco else None,
        }
        for ano, total, preco in por_ano
    ]
    return itens, dy


def destaques(
    conn: Connection, limite: int, volume_financeiro_minimo: Decimal
) -> tuple[date | None, list[dict], list[dict]]:
    linhas = (
        conn.execute(
            text(
                """
                WITH ult AS (SELECT max(data) AS d FROM cotacoes_diarias),
                     ant AS (SELECT max(data) AS d FROM cotacoes_diarias
                             WHERE data < (SELECT d FROM ult))
                SELECT c.data, a.ticker, a.nome, a.tipo, c.fechamento,
                       round(((c.fechamento / p.fechamento - 1) * 100)::numeric, 2) AS variacao
                FROM cotacoes_diarias c
                JOIN cotacoes_diarias p ON p.ativo_id = c.ativo_id AND p.data = (SELECT d FROM ant)
                JOIN ativos a ON a.ativo_id = c.ativo_id
                WHERE c.data = (SELECT d FROM ult) AND a.ativo
                  AND c.volume * c.fechamento >= :minimo
                """
            ),
            {"minimo": volume_financeiro_minimo},
        )
        .mappings()
        .all()
    )
    if not linhas:
        return None, [], []
    itens = [dict(r) | {"variacao": float(r["variacao"])} for r in linhas]
    altas = sorted((i for i in itens if i["variacao"] > 0), key=lambda i: -i["variacao"])
    baixas = sorted((i for i in itens if i["variacao"] < 0), key=lambda i: i["variacao"])
    return linhas[0]["data"], altas[:limite], baixas[:limite]


def execucoes(conn: Connection, limite: int) -> list[RowMapping]:
    return list(
        conn.execute(
            text(
                """
                SELECT execucao_id, tipo, iniciado_em, finalizado_em, status, ativos_ok,
                       ativos_erro, detalhes
                FROM execucoes_job ORDER BY iniciado_em DESC, execucao_id DESC LIMIT :l
                """
            ),
            {"l": limite},
        ).mappings()
    )


def analise(
    conn: Connection, ativo_id: int
) -> tuple[RowMapping | None, list[RowMapping], RowMapping | None]:
    metricas = (
        conn.execute(
            text(
                "SELECT *, volume_financeiro_20d::float AS volume_financeiro_20d, "
                "valor_mercado::float AS valor_mercado FROM metricas_ativo WHERE ativo_id = :a"
            ),
            {"a": ativo_id},
        )
        .mappings()
        .one_or_none()
    )
    insights = list(
        conn.execute(
            text(
                "SELECT codigo, categoria, tom, titulo, texto, data FROM insights "
                "WHERE ativo_id = :a ORDER BY prioridade DESC, codigo"
            ),
            {"a": ativo_id},
        ).mappings()
    )
    cenario = (
        conn.execute(
            text("SELECT data, atr14, niveis, cenarios FROM cenarios WHERE ativo_id = :a"),
            {"a": ativo_id},
        )
        .mappings()
        .one_or_none()
    )
    return metricas, insights, cenario
