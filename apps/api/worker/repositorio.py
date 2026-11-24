"""Acesso ao banco do worker. Todas as gravações são upserts idempotentes."""

import json
import math
from collections.abc import Iterable, Sequence
from datetime import date, timedelta
from decimal import Decimal

import pandas as pd
from sqlalchemy import Connection, bindparam, text

from dominio.indicadores import COLUNAS
from dominio.modelos import EVENTOS_SOCIETARIOS, AtivoInfo, Candle, Fundamentos, Provento

# ativos


def contar_ativos(conn: Connection) -> int:
    return conn.execute(text("SELECT count(*) FROM ativos")).scalar_one()


def sincronizar_ativos(conn: Connection, ativos: Sequence[AtivoInfo]) -> dict:
    """Insere/atualiza o catálogo e marca `ativo=false` nos tickers que sumiram."""
    if not ativos:
        return {"inseridos_ou_atualizados": 0, "desativados": 0}
    conn.execute(
        text(
            """
            INSERT INTO ativos (ticker, nome, tipo, setor, segmento, logo_url, ativo)
            VALUES (:ticker, :nome, :tipo, :setor, :segmento, :logo_url, true)
            ON CONFLICT (ticker) DO UPDATE SET
              nome = EXCLUDED.nome, tipo = EXCLUDED.tipo,
              setor = COALESCE(EXCLUDED.setor, ativos.setor),
              segmento = COALESCE(EXCLUDED.segmento, ativos.segmento),
              logo_url = COALESCE(EXCLUDED.logo_url, ativos.logo_url),
              ativo = true, atualizado_em = now()
            """
        ),
        [
            {
                "ticker": a.ticker,
                "nome": a.nome,
                "tipo": a.tipo,
                "setor": a.setor,
                "segmento": a.segmento,
                "logo_url": a.logo_url,
            }
            for a in ativos
        ],
    )
    desativados = conn.execute(
        text(
            """
            UPDATE ativos SET ativo = false, atualizado_em = now()
            WHERE ativo AND ticker NOT IN :tickers
            """
        ).bindparams(bindparam("tickers", expanding=True)),
        {"tickers": [a.ticker for a in ativos]},
    ).rowcount
    return {"inseridos_ou_atualizados": len(ativos), "desativados": desativados}


def listar_ativos_ativos(
    conn: Connection, tickers: Iterable[str] | None = None
) -> list[tuple[int, str]]:
    sql = "SELECT ativo_id, ticker FROM ativos WHERE ativo"
    params: dict = {}
    if tickers is not None:
        sql += " AND ticker IN :tickers"
        params["tickers"] = [t.upper() for t in tickers]
    stmt = text(sql + " ORDER BY ticker")
    if tickers is not None:
        stmt = stmt.bindparams(bindparam("tickers", expanding=True))
    return [(r.ativo_id, r.ticker) for r in conn.execute(stmt, params)]


# cotações


def _candle(r) -> Candle:
    return Candle(
        r.data, r.abertura, r.maxima, r.minima, r.fechamento, r.fechamento_ajustado, r.volume
    )


def ultima_cotacao(conn: Connection, ativo_id: int) -> Candle | None:
    r = conn.execute(
        text("SELECT * FROM cotacoes_diarias WHERE ativo_id = :a ORDER BY data DESC LIMIT 1"),
        {"a": ativo_id},
    ).first()
    return _candle(r) if r else None


def primeira_data(conn: Connection, ativo_id: int) -> date | None:
    return conn.execute(
        text("SELECT min(data) FROM cotacoes_diarias WHERE ativo_id = :a"), {"a": ativo_id}
    ).scalar_one()


def upsert_cotacoes(conn: Connection, ativo_id: int, candles: Sequence[Candle]) -> int:
    if not candles:
        return 0
    conn.execute(
        text(
            """
            INSERT INTO cotacoes_diarias
              (ativo_id, data, abertura, maxima, minima, fechamento, fechamento_ajustado, volume)
            VALUES (:a, :data, :abertura, :maxima, :minima, :fechamento, :fechamento_ajustado,
                    :volume)
            ON CONFLICT (ativo_id, data) DO UPDATE SET
              abertura = EXCLUDED.abertura, maxima = EXCLUDED.maxima,
              minima = EXCLUDED.minima, fechamento = EXCLUDED.fechamento,
              fechamento_ajustado = EXCLUDED.fechamento_ajustado, volume = EXCLUDED.volume
            """
        ),
        [
            {
                "a": ativo_id,
                "data": c.data,
                "abertura": c.abertura,
                "maxima": c.maxima,
                "minima": c.minima,
                "fechamento": c.fechamento,
                "fechamento_ajustado": c.fechamento_ajustado,
                "volume": c.volume,
            }
            for c in candles
        ],
    )
    return len(candles)


def carregar_ohlcv(conn: Connection, ativo_id: int, desde: date | None = None) -> pd.DataFrame:
    sql = (
        "SELECT data, maxima, minima, fechamento, volume FROM cotacoes_diarias WHERE ativo_id = :a"
    )
    params: dict = {"a": ativo_id}
    if desde is not None:
        sql += " AND data >= :desde"
        params["desde"] = desde
    linhas = conn.execute(text(sql + " ORDER BY data"), params).all()
    df = pd.DataFrame(linhas, columns=["data", "maxima", "minima", "fechamento", "volume"])
    return df.set_index("data")


def ultimo_fechamento(conn: Connection, ativo_id: int) -> Decimal | None:
    c = ultima_cotacao(conn, ativo_id)
    return c.fechamento if c else None


# proventos


def chaves_proventos(conn: Connection, ativo_id: int) -> set[tuple[str, date]]:
    linhas = conn.execute(
        text("SELECT tipo, data_com FROM proventos WHERE ativo_id = :a"), {"a": ativo_id}
    )
    return {(r.tipo, r.data_com) for r in linhas}


def datas_eventos_societarios(conn: Connection, ativo_id: int) -> list[date]:
    linhas = conn.execute(
        text("SELECT data_com FROM proventos WHERE ativo_id = :a AND tipo IN :tipos").bindparams(
            bindparam("tipos", expanding=True)
        ),
        {"a": ativo_id, "tipos": sorted(EVENTOS_SOCIETARIOS)},
    )
    return [r.data_com for r in linhas]


def upsert_proventos(conn: Connection, ativo_id: int, proventos: Sequence[Provento]) -> int:
    if not proventos:
        return 0
    conn.execute(
        text(
            """
            INSERT INTO proventos (ativo_id, tipo, data_com, data_pagamento, valor)
            VALUES (:a, :tipo, :data_com, :data_pagamento, :valor)
            ON CONFLICT (ativo_id, tipo, data_com) DO UPDATE SET
              data_pagamento = COALESCE(EXCLUDED.data_pagamento, proventos.data_pagamento),
              valor = EXCLUDED.valor
            """
        ),
        [
            {
                "a": ativo_id,
                "tipo": p.tipo,
                "data_com": p.data_com,
                "data_pagamento": p.data_pagamento,
                "valor": p.valor,
            }
            for p in proventos
        ],
    )
    return len(proventos)


def soma_proventos_12m(conn: Connection, ativo_id: int, referencia: date) -> Decimal:
    return conn.execute(
        text(
            """
            SELECT COALESCE(sum(valor), 0) FROM proventos
            WHERE ativo_id = :a AND tipo IN ('dividendo','jcp','rendimento')
              AND data_com > :inicio AND data_com <= :fim
            """
        ),
        {"a": ativo_id, "inicio": referencia - timedelta(days=365), "fim": referencia},
    ).scalar_one()


# indicadores


def upsert_indicadores(conn: Connection, ativo_id: int, df: pd.DataFrame) -> int:
    if df.empty:
        return 0

    def limpar(v) -> float | None:
        return None if v is None or (isinstance(v, float) and math.isnan(v)) else float(v)

    linhas = [
        {"a": ativo_id, "data": idx, **{c: limpar(row[c]) for c in COLUNAS}}
        for idx, row in df.iterrows()
    ]
    colunas = ", ".join(COLUNAS)
    valores = ", ".join(f":{c}" for c in COLUNAS)
    atualiza = ", ".join(f"{c} = EXCLUDED.{c}" for c in COLUNAS)
    conn.execute(
        text(
            f"""
            INSERT INTO indicadores_diarios (ativo_id, data, {colunas})
            VALUES (:a, :data, {valores})
            ON CONFLICT (ativo_id, data) DO UPDATE SET {atualiza}
            """
        ),
        linhas,
    )
    return len(linhas)


# fundamentos


def upsert_fundamentos(conn: Connection, ativo_id: int, f: Fundamentos) -> None:
    conn.execute(
        text(
            """
            INSERT INTO fundamentos (ativo_id, data_referencia, pl, pvp, dy_12m, roe,
              margem_liquida, div_liq_ebitda, vpa, lpa, valor_mercado, extras)
            VALUES (:a, :data_referencia, :pl, :pvp, :dy_12m, :roe, :margem_liquida,
              :div_liq_ebitda, :vpa, :lpa, :valor_mercado, CAST(:extras AS JSONB))
            ON CONFLICT (ativo_id, data_referencia) DO UPDATE SET
              pl = EXCLUDED.pl, pvp = EXCLUDED.pvp, dy_12m = EXCLUDED.dy_12m,
              roe = EXCLUDED.roe, margem_liquida = EXCLUDED.margem_liquida,
              div_liq_ebitda = EXCLUDED.div_liq_ebitda, vpa = EXCLUDED.vpa,
              lpa = EXCLUDED.lpa, valor_mercado = EXCLUDED.valor_mercado,
              extras = EXCLUDED.extras
            """
        ),
        {
            "a": ativo_id,
            "data_referencia": f.data_referencia,
            "pl": f.pl,
            "pvp": f.pvp,
            "dy_12m": f.dy_12m,
            "roe": f.roe,
            "margem_liquida": f.margem_liquida,
            "div_liq_ebitda": f.div_liq_ebitda,
            "vpa": f.vpa,
            "lpa": f.lpa,
            "valor_mercado": f.valor_mercado,
            "extras": json.dumps(f.extras),
        },
    )


# execuções do job


def iniciar_execucao(conn: Connection, tipo: str) -> int:
    return conn.execute(
        text("INSERT INTO execucoes_job (tipo) VALUES (:t) RETURNING execucao_id"), {"t": tipo}
    ).scalar_one()


def finalizar_execucao(
    conn: Connection, execucao_id: int, status: str, ok: int, erro: int, detalhes: dict
) -> None:
    conn.execute(
        text(
            """
            UPDATE execucoes_job SET finalizado_em = now(), status = :s, ativos_ok = :ok,
              ativos_erro = :erro, detalhes = CAST(:d AS JSONB)
            WHERE execucao_id = :id
            """
        ),
        {
            "id": execucao_id,
            "s": status,
            "ok": ok,
            "erro": erro,
            "d": json.dumps(detalhes, default=str),
        },
    )
