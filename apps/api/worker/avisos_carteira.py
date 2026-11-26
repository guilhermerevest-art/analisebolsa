"""Avisos sobre a carteira no fim do EOD: proventos pagos, data com chegando, DARF a vencer e
renda fixa vencendo. Só para quem tem push ou WhatsApp pronto e não desligou o tipo de aviso.

Cada aviso tem uma chave única por usuário, então sai uma vez só; o que não foi entregue num
canal volta no próximo EOD (até 7 dias depois).
"""

import logging
from datetime import date, timedelta
from itertools import groupby

from sqlalchemy import Connection, Engine, text

from app import carteira as cart
from app.notificacao import Canais
from app.notificacoes import enviar_push_para
from dominio import avisos_carteira as av
from dominio.alertas import Disparo

log = logging.getLogger("worker.avisos_carteira")
DIAS_REENVIO = 7

_CANAL_PRONTO = """
SELECT user_id FROM push_inscricoes
UNION
SELECT user_id FROM whatsapp WHERE ativo AND confirmado_em IS NOT NULL
"""


def _preferencias(conn: Connection) -> dict[str, set[str]]:
    usuarios = [r[0] for r in conn.execute(text(_CANAL_PRONTO))]
    prefs = {u: set(av.TIPOS) for u in usuarios}
    for r in conn.execute(
        text("SELECT * FROM avisos_carteira_pref WHERE user_id = ANY(:u)"), {"u": usuarios}
    ).mappings():
        prefs[r["user_id"]] = {t for t in av.TIPOS if r[t]}
    return {u: p for u, p in prefs.items() if p}


def avisos_do_usuario(
    conn: Connection, user_id: str, tipos: set[str], hoje: date
) -> list[av.Aviso]:
    saida: list[av.Aviso] = []
    carteiras = conn.execute(
        text("SELECT carteira_id, nome FROM carteiras WHERE user_id = :u ORDER BY carteira_id"),
        {"u": user_id},
    ).all()
    for cid, nome in carteiras:
        if tipos & {"proventos", "data_com"}:
            resumo = cart.resumo(conn, user_id, cid, hoje)
            if "proventos" in tipos:
                for p in resumo["proventos"]:
                    pag = p["data_pagamento"]
                    if (
                        pag
                        and hoje - timedelta(days=3) <= pag <= hoje
                        and p["tipo"] in av.NOMES_PROVENTO
                        and p["total"] > 0
                    ):
                        saida.append(
                            av.provento_pago(
                                cid, nome, p["ticker"], p["tipo"], p["data_com"], pag, p["total"]
                            )
                        )
            tickers = [p["ticker"] for p in resumo["posicoes"]]
            if "data_com" in tipos and tickers:
                for r in conn.execute(
                    text(
                        "SELECT a.ticker, p.tipo, p.data_com, p.valor, p.data_pagamento "
                        "FROM proventos p JOIN ativos a USING (ativo_id) "
                        "WHERE a.ticker = ANY(:t) AND p.tipo = ANY(:tipos) "
                        "AND p.data_com BETWEEN :hoje AND :ate ORDER BY p.data_com, a.ticker"
                    ),
                    {
                        "t": tickers,
                        "tipos": list(av.NOMES_PROVENTO),
                        "hoje": hoje,
                        "ate": hoje + timedelta(days=av.DIAS_DATA_COM),
                    },
                ):
                    saida.append(av.data_com(*r))
        if "darf" in tipos:
            for m in cart.imposto(conn, user_id, cid)["meses"]:
                venc = m["vencimento"]
                if m["darf"] > 0 and venc and hoje <= venc <= hoje + timedelta(days=av.DIAS_DARF):
                    saida.append(av.darf(cid, nome, m["mes"], m["darf"], venc))
        if "vencimentos" in tipos:
            for iid, nome_inv, venc in conn.execute(
                text(
                    "SELECT investimento_id, nome, vencimento FROM investimentos "
                    "WHERE carteira_id = :c AND resgate_data IS NULL "
                    "AND vencimento BETWEEN :hoje AND :ate"
                ),
                {"c": cid, "hoje": hoje, "ate": hoje + timedelta(days=av.DIAS_VENCIMENTO)},
            ):
                saida.append(av.vencimento(cid, nome, iid, nome_inv, venc))
    return saida


def gerar_avisos(engine: Engine, hoje: date) -> int:
    """Grava os avisos novos; devolve quantos entraram."""
    novos = 0
    with engine.connect() as conn:
        prefs = _preferencias(conn)
    for user_id, tipos in prefs.items():
        try:
            with engine.begin() as conn:
                for a in avisos_do_usuario(conn, user_id, tipos, hoje):
                    novos += conn.execute(
                        text(
                            "INSERT INTO avisos_carteira (user_id, chave, tipo, data, texto, url) "
                            "VALUES (:u, :c, :t, :d, :x, :l) ON CONFLICT DO NOTHING"
                        ),
                        {
                            "u": user_id,
                            "c": a.chave,
                            "t": a.tipo,
                            "d": a.data,
                            "x": a.texto,
                            "l": a.url,
                        },
                    ).rowcount
        except Exception:  # uma carteira com problema não impede as outras
            log.exception("avisos: falha num usuário")
    return novos


_PENDENTES = f"""
SELECT v.aviso_id, v.user_id, v.tipo, v.chave, v.data, v.texto, v.url
FROM avisos_carteira v
WHERE v.criado_em >= now() - interval '{DIAS_REENVIO} days'
  AND NOT EXISTS (SELECT 1 FROM avisos_carteira_envios e
                  WHERE e.aviso_id = v.aviso_id AND e.canal = :canal)
  AND {{filtro}}
ORDER BY v.user_id, v.aviso_id
"""
FILTRO = {
    "push": """EXISTS (SELECT 1 FROM push_inscricoes p WHERE p.user_id = v.user_id
               AND v.criado_em >= p.criado_em)""",
    "whatsapp": """EXISTS (SELECT 1 FROM whatsapp w WHERE w.user_id = v.user_id
                   AND w.ativo AND w.confirmado_em IS NOT NULL
                   AND v.criado_em >= w.confirmado_em)""",
}


def _por_usuario(engine: Engine, canal: str, enviar) -> dict:
    with engine.connect() as conn:
        pendentes = (
            conn.execute(text(_PENDENTES.format(filtro=FILTRO[canal])), {"canal": canal})
            .mappings()
            .all()
        )
    enviados = falhas = 0
    for user_id, grupo in groupby(pendentes, key=lambda r: r["user_id"]):
        linhas = list(grupo)
        avisos = [av.Aviso(r["tipo"], r["chave"], r["data"], r["texto"], r["url"]) for r in linhas]
        try:
            ok = enviar(user_id, avisos)
        except Exception:
            log.exception("avisos: falha no %s de um usuário", canal)
            ok = False
        if not ok:
            falhas += 1
            continue
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO avisos_carteira_envios (aviso_id, canal) VALUES (:a, :c) "
                    "ON CONFLICT DO NOTHING"
                ),
                [{"a": r["aviso_id"], "c": canal} for r in linhas],
            )
        enviados += 1
    return {"enviados": enviados, "falhas": falhas, "pendentes": len(pendentes)}


def enviar_avisos(engine: Engine, canais: Canais, site: str) -> dict:
    res: dict = {}
    if canais.push is not None:
        push = canais.push
        res["push"] = _por_usuario(
            engine,
            "push",
            lambda u, avs: enviar_push_para(engine, push, u, av.compor_push(avs)) > 0,
        )
    if canais.whatsapp is not None:
        wa = canais.whatsapp
        link = f"{site.rstrip('/')}/carteira"

        def enviar_whatsapp(user_id: str, avisos: list[av.Aviso]) -> bool:
            with engine.connect() as conn:
                telefone = conn.execute(
                    text("SELECT telefone FROM whatsapp WHERE user_id = :u"), {"u": user_id}
                ).scalar_one()
            if hasattr(wa, "enviar_texto"):  # Evolution: mensagem livre
                wa.enviar_texto(telefone, av.compor_whatsapp(avisos, link))
            else:  # Meta: o modelo aprovado dos alertas
                wa.enviar_alertas(telefone, [Disparo("", a.data, a.texto) for a in avisos], link)
            return True

        res["whatsapp"] = _por_usuario(engine, "whatsapp", enviar_whatsapp)
    return res


def processar_avisos(engine: Engine, canais: Canais, site: str, hoje: date) -> dict:
    """Gera e envia; nunca levanta exceção (o EOD segue de pé)."""
    try:
        return {"novos": gerar_avisos(engine, hoje), **enviar_avisos(engine, canais, site)}
    except Exception as e:
        log.exception("avisos: falha")
        return {"erro": type(e).__name__}
