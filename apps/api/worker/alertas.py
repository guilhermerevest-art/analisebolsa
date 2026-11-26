"""Alertas no fim do EOD: avalia, grava os disparos e envia por push e WhatsApp.

`python -m worker.alertas` roda as duas partes sozinho (modo `alertas` do workflow Worker).
Cada canal anda sozinho: falha num não impede o outro, e o disparo que não saiu por um canal
volta no próximo EOD (até 7 dias depois). Canal sem configuração é pulado.
"""

import logging
import sys
from itertools import groupby

from sqlalchemy import Engine, text

from app.config import get_settings
from app.db import get_engine
from app.notificacao import Canais, EnviadorWhatsApp, canais_configurados
from app.notificacoes import enviar_push_para
from dominio.alertas import Disparo, Pregao, Regra, avaliar, compor_push, compor_whatsapp

log = logging.getLogger("worker.alertas")
DIAS_REENVIO = 7

# Último pregão de cada ativo com alerta ligado, o fechamento anterior e os sinais do dia.
# Só pregões a partir do dia da criação do alerta e depois do último disparo.
SQL_CANDIDATOS = """
SELECT al.alerta_id, a.ticker, al.tipo, al.parametro, al.codigo,
       u.data, u.fechamento, u.anterior,
       ARRAY(SELECT i.codigo FROM insights i
             WHERE i.ativo_id = al.ativo_id AND i.data = u.data) AS insights
FROM alertas al
JOIN ativos a USING (ativo_id)
CROSS JOIN LATERAL (
  SELECT c.data, c.fechamento,
         (SELECT c2.fechamento FROM cotacoes_diarias c2
          WHERE c2.ativo_id = al.ativo_id AND c2.data < c.data
          ORDER BY c2.data DESC LIMIT 1) AS anterior
  FROM cotacoes_diarias c
  WHERE c.ativo_id = al.ativo_id
  ORDER BY c.data DESC LIMIT 1
) u
WHERE al.ativo
  AND u.data >= (al.criado_em AT TIME ZONE 'America/Sao_Paulo')::date
  AND (al.ultimo_disparo IS NULL OR al.ultimo_disparo < u.data)
"""


def avaliar_alertas(engine: Engine) -> int:
    """Grava os disparos do último pregão. Devolve quantos dispararam."""
    disparados = 0
    with engine.begin() as conn:
        for r in conn.execute(text(SQL_CANDIDATOS)).mappings():
            regra = Regra(r["ticker"], r["tipo"], r["parametro"], r["codigo"])
            pregao = Pregao(
                r["data"],
                float(r["fechamento"]),
                float(r["anterior"]) if r["anterior"] is not None else None,
                frozenset(r["insights"]),
            )
            texto = avaliar(regra, pregao)
            if texto is None:
                continue
            conn.execute(
                text(
                    "INSERT INTO alertas_disparos (alerta_id, data, texto) VALUES (:a, :d, :t) "
                    "ON CONFLICT DO NOTHING"
                ),
                {"a": r["alerta_id"], "d": r["data"], "t": texto},
            )
            conn.execute(
                text("UPDATE alertas SET ultimo_disparo = :d WHERE alerta_id = :a"),
                {"a": r["alerta_id"], "d": r["data"]},
            )
            disparados += 1
    return disparados


# Disparos ainda não entregues num canal, de usuários com esse canal pronto. Só entram
# disparos a partir do dia em que o canal foi ligado, para não chegar uma semana de alertas
# antigos de uma vez.
_PENDENTES = f"""
SELECT d.alerta_id, d.data, d.texto, a.ticker, al.user_id
FROM alertas_disparos d
JOIN alertas al USING (alerta_id)
JOIN ativos a ON a.ativo_id = al.ativo_id
WHERE d.data >= current_date - {DIAS_REENVIO}
  AND NOT EXISTS (SELECT 1 FROM alertas_envios e
                  WHERE e.alerta_id = d.alerta_id AND e.data = d.data AND e.canal = :canal)
  AND {{filtro}}
ORDER BY al.user_id, d.data, a.ticker
"""
FILTRO = {
    "push": """EXISTS (SELECT 1 FROM push_inscricoes p WHERE p.user_id = al.user_id
               AND d.data >= (p.criado_em AT TIME ZONE 'America/Sao_Paulo')::date)""",
    "whatsapp": """EXISTS (SELECT 1 FROM whatsapp w WHERE w.user_id = al.user_id
                   AND w.ativo AND w.confirmado_em IS NOT NULL
                   AND d.data >= (w.confirmado_em AT TIME ZONE 'America/Sao_Paulo')::date)""",
}


def _pendentes(engine: Engine, canal: str) -> list:
    with engine.connect() as conn:
        sql = _PENDENTES.format(filtro=FILTRO[canal])
        return conn.execute(text(sql), {"canal": canal}).mappings().all()


def _marcar(engine: Engine, linhas: list, canal: str) -> None:
    with engine.begin() as conn:
        for r in linhas:
            conn.execute(
                text(
                    "INSERT INTO alertas_envios (alerta_id, data, canal) VALUES (:a, :d, :c) "
                    "ON CONFLICT DO NOTHING"
                ),
                {"a": r["alerta_id"], "d": r["data"], "c": canal},
            )


def _por_usuario(engine: Engine, canal: str, enviar) -> dict:
    pendentes = _pendentes(engine, canal)
    enviados = falhas = 0
    for user_id, grupo in groupby(pendentes, key=lambda r: r["user_id"]):
        linhas = list(grupo)
        disparos = [Disparo(r["ticker"], r["data"], r["texto"]) for r in linhas]
        try:
            ok = enviar(user_id, disparos)
        except Exception:
            log.exception("alertas: falha no %s de um usuário", canal)
            ok = False
        if ok:
            _marcar(engine, linhas, canal)
            enviados += 1
        else:
            falhas += 1
    return {"enviados": enviados, "falhas": falhas, "pendentes": len(pendentes)}


def enviar_pendentes(engine: Engine, canais: Canais, site: str) -> dict:
    res: dict = {}
    if canais.push is None:
        res["push"] = "não configurado"
    else:
        push = canais.push
        res["push"] = _por_usuario(
            engine, "push", lambda u, ds: enviar_push_para(engine, push, u, compor_push(ds)) > 0
        )
    if canais.whatsapp is None:
        res["whatsapp"] = "não configurado"
    else:
        wa: EnviadorWhatsApp = canais.whatsapp

        def enviar_whatsapp(user_id: str, disparos: list[Disparo]) -> bool:
            with engine.connect() as conn:
                telefone = conn.execute(
                    text("SELECT telefone FROM whatsapp WHERE user_id = :u"), {"u": user_id}
                ).scalar_one()
            wa.enviar_alertas(telefone, compor_whatsapp(disparos), f"{site.rstrip('/')}/alertas")
            return True

        res["whatsapp"] = _por_usuario(engine, "whatsapp", enviar_whatsapp)
    return res


def processar_alertas(engine: Engine, canais: Canais, site: str) -> dict:
    """Avalia e envia; nunca levanta exceção (o EOD segue de pé)."""
    try:
        disparados = avaliar_alertas(engine)
        return {"disparados": disparados, **enviar_pendentes(engine, canais, site)}
    except Exception as e:
        log.exception("alertas: falha")
        return {"erro": type(e).__name__}


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    settings = get_settings()
    res = processar_alertas(get_engine(), canais_configurados(settings), settings.url_publica)
    log.info("alertas: %s", res)
    return 1 if "erro" in res else 0


if __name__ == "__main__":
    sys.exit(main())
