"""Consultas das funcionalidades de usuário (Fase 3). Toda consulta filtra pelo usuário."""

from datetime import date

from sqlalchemy import Connection, RowMapping, text

from app.erros import Problema
from app.schemas import MetricasAtivo
from app.screener import COLUNAS_SAIDA

LIMITE_WATCHLIST = 100
COLUNAS_METRICAS = list(MetricasAtivo.model_fields)


def exigir_usuario_existente(conn: Connection, user_id: str) -> None:
    if not conn.execute(text("SELECT 1 FROM users WHERE id = :u"), {"u": user_id}).first():
        raise Problema(401, "usuário não encontrado")


def watchlist(conn: Connection, user_id: str) -> list[dict]:
    linhas = conn.execute(
        text(
            f"""
            SELECT w.criado_em AS adicionado_em, m.ativo_id IS NOT NULL AS tem_metricas,
                   {COLUNAS_SAIDA}
            FROM watchlist w
            JOIN ativos a USING (ativo_id)
            LEFT JOIN metricas_ativo m USING (ativo_id)
            WHERE w.user_id = :u
            ORDER BY a.ticker
            """
        ),
        {"u": user_id},
    ).mappings()
    saida = []
    for r in linhas:
        item = {k: r[k] for k in ("ticker", "nome", "tipo", "setor", "logo_url", "adicionado_em")}
        item["metricas"] = {k: r[k] for k in COLUNAS_METRICAS} if r["tem_metricas"] else None
        saida.append(item)
    return saida


def na_watchlist(conn: Connection, user_id: str, ativo_id: int) -> RowMapping | None:
    return (
        conn.execute(
            text("SELECT criado_em FROM watchlist WHERE user_id = :u AND ativo_id = :a"),
            {"u": user_id, "a": ativo_id},
        )
        .mappings()
        .one_or_none()
    )


def adicionar_watchlist(conn: Connection, user_id: str, ativo_id: int) -> bool:
    """Devolve True se o ativo entrou agora, False se já estava na lista."""
    if na_watchlist(conn, user_id, ativo_id):
        return False
    exigir_usuario_existente(conn, user_id)
    total = conn.execute(
        text("SELECT count(*) FROM watchlist WHERE user_id = :u"), {"u": user_id}
    ).scalar_one()
    if total >= LIMITE_WATCHLIST:
        raise Problema(409, f"a watchlist aceita até {LIMITE_WATCHLIST} ativos")
    conn.execute(
        text(
            "INSERT INTO watchlist (user_id, ativo_id) VALUES (:u, :a) "
            "ON CONFLICT (user_id, ativo_id) DO NOTHING"
        ),
        {"u": user_id, "a": ativo_id},
    )
    return True


def remover_watchlist(conn: Connection, user_id: str, ativo_id: int) -> bool:
    res = conn.execute(
        text("DELETE FROM watchlist WHERE user_id = :u AND ativo_id = :a"),
        {"u": user_id, "a": ativo_id},
    )
    return res.rowcount > 0


def serie_indice(conn: Connection, serie: str, inicio: date, fim: date) -> list[RowMapping]:
    return list(
        conn.execute(
            text(
                "SELECT data, valor FROM indices WHERE serie = :s AND data BETWEEN :i AND :f "
                "ORDER BY data"
            ),
            {"s": serie, "i": inicio, "f": fim},
        ).mappings()
    )
