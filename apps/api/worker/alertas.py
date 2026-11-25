"""Alertas no fim do EOD: avalia, grava os disparos e envia um e-mail por usuário.

`python -m worker.alertas` roda as duas partes sozinho (modo `alertas` do workflow Worker).
Falha no envio não derruba o job: o disparo fica com `enviado_em` nulo e volta no próximo EOD
(até 7 dias depois).
"""

import logging
import sys
from itertools import groupby

from sqlalchemy import Engine, text

from app.config import get_settings
from app.db import get_engine
from dominio.alertas import Disparo, Pregao, Regra, avaliar, compor_email
from worker.notificacao import Enviador, enviador_configurado

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


SQL_PENDENTES = f"""
SELECT d.alerta_id, d.data, d.texto, a.ticker, u.id AS user_id, u.email
FROM alertas_disparos d
JOIN alertas al USING (alerta_id)
JOIN ativos a ON a.ativo_id = al.ativo_id
JOIN users u ON u.id = al.user_id
WHERE d.enviado_em IS NULL AND u.email IS NOT NULL
  AND d.data >= current_date - {DIAS_REENVIO}
ORDER BY u.id, d.data, a.ticker
"""


def enviar_pendentes(engine: Engine, enviador: Enviador | None, site: str) -> dict:
    with engine.connect() as conn:
        pendentes = conn.execute(text(SQL_PENDENTES)).mappings().all()
    if not pendentes:
        return {"enviados": 0, "pendentes": 0}
    if enviador is None:
        log.warning("alertas: SMTP não configurado; %d disparos aguardando envio", len(pendentes))
        return {"enviados": 0, "pendentes": len(pendentes), "smtp": "não configurado"}

    enviados = falhas = 0
    for _, grupo in groupby(pendentes, key=lambda r: r["user_id"]):
        linhas = list(grupo)
        assunto, corpo, html = compor_email(
            [Disparo(r["ticker"], r["data"], r["texto"]) for r in linhas], site
        )
        try:
            enviador.enviar(linhas[0]["email"], assunto, corpo, html)
        except Exception:  # um usuário com problema não impede os outros
            log.exception("alertas: falha ao enviar para um usuário")
            falhas += 1
            continue
        with engine.begin() as conn:
            for r in linhas:
                conn.execute(
                    text(
                        "UPDATE alertas_disparos SET enviado_em = now() "
                        "WHERE alerta_id = :a AND data = :d"
                    ),
                    {"a": r["alerta_id"], "d": r["data"]},
                )
        enviados += 1
    return {"enviados": enviados, "falhas": falhas, "pendentes": len(pendentes)}


def processar_alertas(engine: Engine, enviador: Enviador | None, site: str) -> dict:
    """Avalia e envia; nunca levanta exceção (o EOD segue de pé)."""
    try:
        disparados = avaliar_alertas(engine)
        return {"disparados": disparados, **enviar_pendentes(engine, enviador, site)}
    except Exception as e:
        log.exception("alertas: falha")
        return {"erro": type(e).__name__}


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    settings = get_settings()
    res = processar_alertas(get_engine(), enviador_configurado(settings), settings.web_internal_url)
    log.info("alertas: %s", res)
    return 1 if "erro" in res else 0


if __name__ == "__main__":
    sys.exit(main())
