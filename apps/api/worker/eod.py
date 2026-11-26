"""Job diário após o pregão: `python -m worker.eod`.

Agendado no GitHub Actions (workflow Worker) com cron `0 22 * * 1-5` (UTC), 19h em Brasília.
"""

import argparse
import logging
import sys
from datetime import date, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import Engine

from app.config import Settings, get_settings
from app.db import get_engine
from app.notificacao import Canais
from fontes.cadeia import CadeiaFontes, criar_cadeia
from worker import repositorio as repo
from worker.alertas import canais_do_worker, processar_alertas
from worker.analise import atualizar_analise
from worker.avisos_carteira import processar_avisos
from worker.fundos import atualizar_fundos
from worker.indices import atualizar_indices, buscadores
from worker.processamento import (
    atualizar_fundamentos,
    processar_ativos,
    revalidar_web,
    sincronizar_catalogo,
)

log = logging.getLogger("worker.eod")
FUSO = ZoneInfo("America/Sao_Paulo")


def hoje_b3() -> date:
    return datetime.now(FUSO).date()


def executar_eod(
    engine: Engine,
    fontes: CadeiaFontes,
    settings: Settings,
    hoje: date,
    *,
    forcar_catalogo: bool = False,
    forcar_fundamentos: bool = False,
    fontes_indices: dict | None = None,
    canais: Canais | None = None,
    dormir=None,
) -> str:
    with engine.begin() as conn:
        vazio = repo.contar_ativos(conn) == 0
    segunda = hoje.weekday() == 0
    if forcar_catalogo or segunda or vazio:
        sincronizar_catalogo(engine, fontes)

    with engine.begin() as conn:
        execucao = repo.iniciar_execucao(conn, "eod")
        ativos = repo.listar_ativos_ativos(conn)
    res = processar_ativos(
        engine, fontes, ativos, hoje, pausa_s=settings.pausa_entre_tickers_s, dormir=dormir
    )

    fundamentos_novos = forcar_fundamentos or segunda or vazio
    if fundamentos_novos:
        atualizar_fundamentos(
            engine, fontes, hoje, pausa_s=settings.pausa_entre_tickers_s, dormir=dormir
        )

    # Análise (Fase 2): todos os ativos quando os fundamentos mudaram, senão só os com
    # pregão ou provento novo.
    with engine.begin() as conn:
        alvo = ativos if fundamentos_novos else repo.ids_por_ticker(conn, res.tickers_atualizados)
    res.detalhes["analise"] = atualizar_analise(engine, alvo)

    if fontes_indices is not None:
        res.detalhes["indices"] = atualizar_indices(engine, hoje, fontes=fontes_indices)
        try:
            res.detalhes["fundos"] = atualizar_fundos(engine, hoje)
        except Exception as e:  # as cotas da CVM não podem derrubar o EOD
            res.detalhes["fundos"] = str(e)[:200]

    res.detalhes["alertas"] = processar_alertas(engine, canais or Canais(), settings.url_publica)
    res.detalhes["avisos_carteira"] = processar_avisos(
        engine, canais or Canais(), settings.url_publica, hoje
    )

    res.detalhes["revalidacao"] = revalidar_web(
        settings.web_internal_url, settings.internal_jwt_secret, res.tickers_atualizados
    )
    res.detalhes["atualizados"] = len(res.tickers_atualizados)
    with engine.begin() as conn:
        repo.finalizar_execucao(conn, execucao, res.status, res.ok, res.erro, res.detalhes)
    log.info("eod %s: %d ok, %d com erro", res.status, res.ok, res.erro)
    return res.status


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Atualização EOD do analisebolsa")
    parser.add_argument("--catalogo", action="store_true", help="força a sincronização do catálogo")
    parser.add_argument("--fundamentos", action="store_true", help="força os fundamentos")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    settings = get_settings()
    engine = get_engine()
    status = executar_eod(
        engine,
        criar_cadeia(settings),
        settings,
        hoje_b3(),
        forcar_catalogo=args.catalogo,
        forcar_fundamentos=args.fundamentos,
        fontes_indices=buscadores(),
        canais=canais_do_worker(engine, settings),
    )
    return 1 if status == "erro" else 0


if __name__ == "__main__":
    sys.exit(main())
