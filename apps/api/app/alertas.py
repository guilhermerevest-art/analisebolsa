"""Alertas e conta do usuário (Fase 3, etapa 5). Toda consulta filtra pelo usuário."""

from sqlalchemy import Connection, RowMapping, text

from app import consultas as q
from app import notificacoes
from app.erros import Problema
from app.usuario import exigir_usuario_existente
from dominio.alertas import INSIGHTS_ALERTA, Regra, descrever

LIMITE_ALERTAS = 30

_SELECT = """
SELECT al.alerta_id AS id, a.ticker, a.nome, al.tipo, al.parametro, al.codigo, al.ativo,
       al.ultimo_disparo, al.criado_em
FROM alertas al JOIN ativos a USING (ativo_id)
"""


def _com_descricao(r: RowMapping) -> dict:
    d = dict(r)
    d["descricao"] = descrever(Regra(r["ticker"], r["tipo"], r["parametro"], r["codigo"]))
    return d


def listar(conn: Connection, user_id: str) -> list[dict]:
    linhas = conn.execute(
        text(_SELECT + " WHERE al.user_id = :u ORDER BY a.ticker, al.alerta_id"), {"u": user_id}
    ).mappings()
    return [_com_descricao(r) for r in linhas]


def obter(conn: Connection, user_id: str, alerta_id: int) -> dict:
    r = (
        conn.execute(
            text(_SELECT + " WHERE al.user_id = :u AND al.alerta_id = :id"),
            {"u": user_id, "id": alerta_id},
        )
        .mappings()
        .one_or_none()
    )
    if r is None:
        raise Problema(404, "alerta não encontrado")
    return _com_descricao(r)


def _ativos(conn: Connection, user_id: str) -> int:
    return conn.execute(
        text("SELECT count(*) FROM alertas WHERE user_id = :u AND ativo"), {"u": user_id}
    ).scalar_one()


def _limite(conn: Connection, user_id: str) -> None:
    if _ativos(conn, user_id) >= LIMITE_ALERTAS:
        raise Problema(409, f"cada conta pode ter até {LIMITE_ALERTAS} alertas ligados")


def criar(
    conn: Connection,
    user_id: str,
    ticker: str,
    tipo: str,
    parametro: float | None,
    codigo: str | None,
) -> dict:
    if tipo == "insight":
        if codigo not in INSIGHTS_ALERTA:
            raise Problema(422, "sinal inválido para alerta")
        parametro = None
    else:
        if parametro is None or parametro <= 0:
            raise Problema(422, "informe um valor maior que zero")
        if tipo == "variacao_dia" and parametro > 100:
            raise Problema(422, "a variação do dia vai até 100%")
        codigo = None
    exigir_usuario_existente(conn, user_id)
    ativo = q.ativo_por_ticker(conn, ticker.upper())
    _limite(conn, user_id)
    novo = conn.execute(
        text(
            "INSERT INTO alertas (user_id, ativo_id, tipo, parametro, codigo) "
            "VALUES (:u, :a, :t, :p, :c) RETURNING alerta_id"
        ),
        {"u": user_id, "a": ativo["ativo_id"], "t": tipo, "p": parametro, "c": codigo},
    ).scalar_one()
    return obter(conn, user_id, novo)


def alterar(conn: Connection, user_id: str, alerta_id: int, ligado: bool) -> dict:
    atual = obter(conn, user_id, alerta_id)
    if ligado and not atual["ativo"]:
        _limite(conn, user_id)
    conn.execute(
        text("UPDATE alertas SET ativo = :v WHERE alerta_id = :id"), {"v": ligado, "id": alerta_id}
    )
    return obter(conn, user_id, alerta_id)


def excluir(conn: Connection, user_id: str, alerta_id: int) -> None:
    obter(conn, user_id, alerta_id)
    conn.execute(text("DELETE FROM alertas WHERE alerta_id = :id"), {"id": alerta_id})


def disparos(conn: Connection, user_id: str, limite: int = 50) -> list[RowMapping]:
    return (
        conn.execute(
            text(
                """
                SELECT d.alerta_id, a.ticker, d.data, d.texto,
                       ARRAY(SELECT e.canal FROM alertas_envios e
                             WHERE e.alerta_id = d.alerta_id AND e.data = d.data
                             ORDER BY e.canal) AS canais
                FROM alertas_disparos d
                JOIN alertas al USING (alerta_id)
                JOIN ativos a ON a.ativo_id = al.ativo_id
                WHERE al.user_id = :u
                ORDER BY d.data DESC, a.ticker
                LIMIT :l
                """
            ),
            {"u": user_id, "l": limite},
        )
        .mappings()
        .all()
    )


# Conta (LGPD): exportar e excluir.


def exportar(conn: Connection, user_id: str) -> dict:
    exigir_usuario_existente(conn, user_id)

    def todos(sql: str) -> list[dict]:
        return [dict(r) for r in conn.execute(text(sql), {"u": user_id}).mappings()]

    usuario = todos(
        'SELECT id, name AS nome, email, "emailVerified" AS email_verificado, plano '
        "FROM users WHERE id = :u"
    )[0]
    return {
        "usuario": usuario,
        "contas_vinculadas": todos(
            'SELECT provider AS provedor FROM accounts WHERE "userId" = :u ORDER BY provider'
        ),
        "watchlist": todos(
            "SELECT a.ticker, w.criado_em FROM watchlist w JOIN ativos a USING (ativo_id) "
            "WHERE w.user_id = :u ORDER BY a.ticker"
        ),
        "carteiras": [
            {
                **c,
                "operacoes": [
                    dict(o)
                    for o in conn.execute(
                        text(
                            "SELECT a.ticker, o.tipo, o.data, o.quantidade, o.preco, o.custos, "
                            "o.criado_em FROM operacoes o JOIN ativos a USING (ativo_id) "
                            "WHERE o.carteira_id = :c ORDER BY o.data, o.operacao_id"
                        ),
                        {"c": c["id"]},
                    ).mappings()
                ],
                "investimentos": [
                    dict(i)
                    for i in conn.execute(
                        text(
                            "SELECT tipo, nome, indexador, taxa, data_aplicacao, valor_aplicado, "
                            "vencimento, isento_ir, cnpj, cotas, resgate_data, resgate_valor, "
                            "criado_em FROM investimentos WHERE carteira_id = :c "
                            "ORDER BY data_aplicacao, investimento_id"
                        ),
                        {"c": c["id"]},
                    ).mappings()
                ],
            }
            for c in todos(
                "SELECT carteira_id AS id, nome, criado_em FROM carteiras "
                "WHERE user_id = :u ORDER BY carteira_id"
            )
        ],
        "alertas": listar(conn, user_id),
        "avisos_carteira": avisos_carteira(conn, user_id),
        "alertas_disparos": [dict(r) for r in disparos(conn, user_id, limite=10_000)],
        **notificacoes.exportar(conn, user_id),
    }


def excluir_conta(conn: Connection, user_id: str) -> None:
    """Apaga o usuário; tudo o que é dele sai junto (ON DELETE CASCADE)."""
    exigir_usuario_existente(conn, user_id)
    conn.execute(text("DELETE FROM users WHERE id = :u"), {"u": user_id})


# Avisos sobre a carteira (Fase 7)

TIPOS_AVISO = ("proventos", "data_com", "darf", "vencimentos")


def avisos_carteira(conn: Connection, user_id: str) -> dict:
    pref = (
        conn.execute(text("SELECT * FROM avisos_carteira_pref WHERE user_id = :u"), {"u": user_id})
        .mappings()
        .first()
    )
    recentes = (
        conn.execute(
            text(
                "SELECT tipo, data, texto, url, criado_em FROM avisos_carteira WHERE user_id = :u "
                "ORDER BY criado_em DESC, aviso_id DESC LIMIT 20"
            ),
            {"u": user_id},
        )
        .mappings()
        .all()
    )
    return {
        "preferencias": {t: pref[t] if pref else True for t in TIPOS_AVISO},
        "recentes": [dict(r) for r in recentes],
    }


def salvar_preferencias(conn: Connection, user_id: str, prefs: dict) -> None:
    exigir_usuario_existente(conn, user_id)
    conn.execute(
        text(
            "INSERT INTO avisos_carteira_pref (user_id, proventos, data_com, darf, vencimentos) "
            "VALUES (:u, :proventos, :data_com, :darf, :vencimentos) ON CONFLICT (user_id) DO "
            "UPDATE SET proventos = EXCLUDED.proventos, data_com = EXCLUDED.data_com, "
            "darf = EXCLUDED.darf, vencimentos = EXCLUDED.vencimentos"
        ),
        {"u": user_id, **{t: bool(prefs[t]) for t in TIPOS_AVISO}},
    )
