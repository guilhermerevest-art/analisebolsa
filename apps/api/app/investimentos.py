"""Renda fixa e fundos na carteira (Fase 7). Toda consulta passa pela carteira do usuário."""

from datetime import date, timedelta

from sqlalchemy import Connection, text

from app import carteira as c
from app.erros import Problema
from dominio.renda_fixa import (
    TIPOS,
    Investimento,
    avaliar,
    descrever_taxa,
    formatar_cnpj,
    normalizar_cnpj,
)

LIMITE = 200

_SELECT = """
SELECT investimento_id AS id, tipo, nome, indexador, taxa, data_aplicacao,
       valor_aplicado::float AS valor_aplicado, vencimento, isento_ir, cnpj,
       cotas::float AS cotas, resgate_data, resgate_valor::float AS resgate_valor
FROM investimentos WHERE carteira_id = :c
"""


def _series(conn: Connection, desde: date) -> tuple[dict, dict]:
    def serie(nome: str, inicio: date) -> dict[date, float]:
        return dict(
            conn.execute(
                text("SELECT data, valor FROM indices WHERE serie = :s AND data >= :i"),
                {"s": nome, "i": inicio},
            ).all()
        )

    return serie("cdi", desde), serie("ipca", date(desde.year, desde.month, 1))


def _cotas(conn: Connection, cnpjs: list[str], desde: date) -> dict[str, dict[date, float]]:
    saida: dict[str, dict[date, float]] = {k: {} for k in cnpjs}
    if cnpjs:
        for cnpj, d, v in conn.execute(
            text("SELECT cnpj, data, cota FROM cotas_fundos WHERE cnpj = ANY(:c) AND data >= :d"),
            {"c": cnpjs, "d": desde - timedelta(days=10)},
        ):
            saida[cnpj][d] = v
    return saida


def listar(conn: Connection, user_id: str, carteira_id: int, hoje: date) -> dict:
    c.obter(conn, user_id, carteira_id)
    linhas = [
        dict(r)
        for r in conn.execute(
            text(_SELECT + " ORDER BY data_aplicacao, investimento_id"), {"c": carteira_id}
        ).mappings()
    ]
    if not linhas:
        return {"itens": [], "totais": {"aplicado": 0, "bruto": 0, "liquido": 0}}
    desde = min(r["data_aplicacao"] for r in linhas)
    cdi, ipca = _series(conn, desde)
    cotas = _cotas(conn, sorted({r["cnpj"] for r in linhas if r["cnpj"]}), desde)

    itens = []
    aplicado = bruto = liquido = 0.0
    for r in linhas:
        inv = Investimento(
            r["tipo"],
            r["data_aplicacao"],
            r["valor_aplicado"],
            r["indexador"],
            r["taxa"],
            r["isento_ir"],
            r["cotas"],
            r["resgate_data"],
            r["resgate_valor"],
        )
        a = avaliar(inv, hoje, cdi, ipca, cotas.get(r["cnpj"]) if r["cnpj"] else None)
        if r["resgate_data"] is None:
            aplicado += r["valor_aplicado"]
            bruto += a.bruto or r["valor_aplicado"]
            liquido += a.liquido if a.liquido is not None else (a.bruto or r["valor_aplicado"])
        itens.append(
            r
            | {
                "tipo_nome": TIPOS[r["tipo"]],
                "descricao_taxa": descrever_taxa(r["indexador"], r["taxa"]),
                "cnpj": formatar_cnpj(r["cnpj"]) if r["cnpj"] else None,
                "cotas": a.cotas if r["tipo"] == "fundo" else None,
                "cotas_informadas": r["cotas"] is not None,
                "avaliado_em": a.data,
                "bruto": a.bruto,
                "ir": a.ir,
                "liquido": a.liquido,
                "rendimento": a.rendimento,
                "aliquota_ir": a.aliquota,
                "observacao": a.observacao,
            }
        )
    return {
        "itens": itens,
        "totais": {
            "aplicado": round(aplicado, 2),
            "bruto": round(bruto, 2),
            "liquido": round(liquido, 2),
        },
    }


def _dados(d: dict, hoje: date) -> dict:
    if d["data_aplicacao"] > hoje:
        raise Problema(422, "a data da aplicação não pode ser no futuro")
    if d.get("vencimento") and d["vencimento"] <= d["data_aplicacao"]:
        raise Problema(422, "o vencimento precisa ser depois da aplicação")
    if (d.get("resgate_data") is None) != (d.get("resgate_valor") is None):
        raise Problema(422, "informe a data e o valor do resgate")
    if d.get("resgate_data") and d["resgate_data"] < d["data_aplicacao"]:
        raise Problema(422, "o resgate precisa ser depois da aplicação")
    if d["tipo"] == "fundo":
        cnpj = normalizar_cnpj(d.get("cnpj") or "")
        if cnpj is None:
            raise Problema(422, "CNPJ do fundo inválido")
        return d | {"cnpj": cnpj, "indexador": None, "taxa": None, "isento_ir": False}
    if d.get("indexador") is None or d.get("taxa") is None:
        raise Problema(422, "informe o indexador e a taxa")
    if d["indexador"] == "cdi" and not 1 <= d["taxa"] <= 300:
        raise Problema(422, "o percentual do CDI vai de 1% a 300%")
    if d["indexador"] != "cdi" and not 0 <= d["taxa"] <= 50:
        raise Problema(422, "a taxa vai de 0% a 50% ao ano")
    return d | {
        "cnpj": None,
        "cotas": None,
        "isento_ir": d.get("isento_ir") or d["tipo"] == "lci_lca",
    }


_CAMPOS = (
    "tipo",
    "nome",
    "indexador",
    "taxa",
    "data_aplicacao",
    "valor_aplicado",
    "vencimento",
    "isento_ir",
    "cnpj",
    "cotas",
    "resgate_data",
    "resgate_valor",
)


def criar(conn: Connection, user_id: str, carteira_id: int, dados: dict, hoje: date) -> int:
    c.obter(conn, user_id, carteira_id)
    n = conn.execute(
        text("SELECT count(*) FROM investimentos WHERE carteira_id = :c"), {"c": carteira_id}
    ).scalar_one()
    if n >= LIMITE:
        raise Problema(409, f"cada carteira aceita até {LIMITE} aplicações")
    d = _dados(dados, hoje)
    return conn.execute(
        text(
            f"INSERT INTO investimentos (carteira_id, {', '.join(_CAMPOS)}) "
            f"VALUES (:c, {', '.join(':' + k for k in _CAMPOS)}) RETURNING investimento_id"
        ),
        {k: d.get(k) for k in _CAMPOS} | {"c": carteira_id},
    ).scalar_one()


def editar(
    conn: Connection, user_id: str, carteira_id: int, inv_id: int, dados: dict, hoje: date
) -> None:
    c.obter(conn, user_id, carteira_id)
    d = _dados(dados, hoje)
    n = conn.execute(
        text(
            f"UPDATE investimentos SET {', '.join(f'{k} = :{k}' for k in _CAMPOS)} "
            "WHERE investimento_id = :i AND carteira_id = :c"
        ),
        {k: d.get(k) for k in _CAMPOS} | {"c": carteira_id, "i": inv_id},
    ).rowcount
    if not n:
        raise Problema(404, "aplicação não encontrada")


def excluir(conn: Connection, user_id: str, carteira_id: int, inv_id: int) -> None:
    c.obter(conn, user_id, carteira_id)
    n = conn.execute(
        text("DELETE FROM investimentos WHERE investimento_id = :i AND carteira_id = :c"),
        {"i": inv_id, "c": carteira_id},
    ).rowcount
    if not n:
        raise Problema(404, "aplicação não encontrada")
