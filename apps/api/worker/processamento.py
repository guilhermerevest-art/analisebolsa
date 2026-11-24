"""Processamento de um ativo e das etapas do job (seção 4 da spec)."""

import logging
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field, replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import httpx
import jwt
from sqlalchemy import Engine

from dominio.ajuste import precisa_rebaixar_historico
from dominio.indicadores import JANELA_AQUECIMENTO_DIAS, calcular_indicadores
from dominio.validacao import validar_candles
from fontes.cadeia import CadeiaFontes
from worker import repositorio as repo

log = logging.getLogger(__name__)
INICIO_HISTORICO = date(2005, 1, 1)


@dataclass
class ResultadoJob:
    ok: int = 0
    erro: int = 0
    detalhes: dict = field(default_factory=lambda: {"erros": {}, "rejeitadas": {}, "alertas": {}})
    tickers_atualizados: list[str] = field(default_factory=list)

    @property
    def status(self) -> str:
        return status_por_contagem(self.ok, self.erro)


def status_por_contagem(ok: int, erro: int) -> str:
    if erro and not ok:
        return "erro"
    return "parcial" if erro else "ok"


def processar_ativo(
    engine: Engine,
    fontes: CadeiaFontes,
    ativo_id: int,
    ticker: str,
    hoje: date,
    desde: date = INICIO_HISTORICO,
) -> dict:
    """Atualiza proventos, cotações e indicadores de um ativo numa transação."""
    with engine.begin() as conn:
        ultima = repo.ultima_cotacao(conn, ativo_id)
        primeira = repo.primeira_data(conn, ativo_id)

        proventos = fontes.proventos(ticker)
        existentes = repo.chaves_proventos(conn, ativo_id)
        novos = [p for p in proventos if (p.tipo, p.data_com) not in existentes]
        repo.upsert_proventos(conn, ativo_id, proventos)
        rebaixar = precisa_rebaixar_historico(novos, primeira)

        # Rebusca o último pregão gravado: se o job rodou com o pregão em
        # andamento, o candle parcial é corrigido pelo upsert.
        inicio = desde if (rebaixar or ultima is None) else ultima.data
        anterior = None if (rebaixar or ultima is None) else ultima
        gravados: list = []
        rejeitadas: list = []
        alertas: list = []
        if inicio <= hoje:
            candles = fontes.cotacoes(ticker, inicio, hoje)
            gravados, rejeitadas, alertas = validar_candles(
                candles,
                anterior=anterior,
                datas_eventos=repo.datas_eventos_societarios(conn, ativo_id),
            )
            repo.upsert_cotacoes(conn, ativo_id, gravados)

        indicadores = 0
        if gravados:
            primeiro_novo = gravados[0].data
            completo = anterior is None
            janela = None if completo else primeiro_novo - timedelta(days=JANELA_AQUECIMENTO_DIAS)
            df = repo.carregar_ohlcv(conn, ativo_id, janela)
            ind = calcular_indicadores(df)
            if not completo:
                ind = ind[ind.index >= primeiro_novo]
            indicadores = repo.upsert_indicadores(conn, ativo_id, ind)

    novas = [c for c in gravados if ultima is None or rebaixar or c.data > ultima.data]
    return {
        "cotacoes": len(novas),
        "rejeitadas": [r.como_dict() for r in rejeitadas],
        "alertas": [r.como_dict() for r in alertas],
        "proventos_novos": len(novos),
        "rebaixado": rebaixar,
        "indicadores": indicadores,
    }


def processar_ativos(
    engine: Engine,
    fontes: CadeiaFontes,
    ativos: Iterable[tuple[int, str]],
    hoje: date,
    *,
    desde: date = INICIO_HISTORICO,
    pausa_s: float = 0.0,
    dormir: Callable[[float], None] | None = None,
) -> ResultadoJob:
    """A falha de um ticker não derruba o job: ele entra em `ativos_erro`."""
    dormir = dormir or time.sleep
    res = ResultadoJob()
    for i, (ativo_id, ticker) in enumerate(ativos):
        if i and pausa_s:
            dormir(pausa_s)
        try:
            r = processar_ativo(engine, fontes, ativo_id, ticker, hoje, desde)
        except Exception as e:
            log.exception("falha em %s", ticker)
            res.erro += 1
            res.detalhes["erros"][ticker] = f"{type(e).__name__}: {e}"[:500]
            continue
        res.ok += 1
        if r["rejeitadas"]:
            res.detalhes["rejeitadas"][ticker] = r["rejeitadas"]
        if r["alertas"]:
            res.detalhes["alertas"][ticker] = r["alertas"]
        if r["cotacoes"] or r["proventos_novos"]:
            res.tickers_atualizados.append(ticker)
    return res


def sincronizar_catalogo(engine: Engine, fontes: CadeiaFontes) -> str:
    with engine.begin() as conn:
        execucao = repo.iniciar_execucao(conn, "catalogo")
    try:
        ativos = fontes.listar_ativos()
        if not ativos:
            raise RuntimeError("catálogo vazio: nenhuma fonte devolveu ativos")
        with engine.begin() as conn:
            detalhes = repo.sincronizar_ativos(conn, ativos)
            repo.finalizar_execucao(conn, execucao, "ok", len(ativos), 0, detalhes)
        return "ok"
    except Exception as e:
        log.exception("falha no catálogo")
        with engine.begin() as conn:
            repo.finalizar_execucao(conn, execucao, "erro", 0, 0, {"erro": str(e)[:500]})
        return "erro"


def atualizar_fundamentos(
    engine: Engine,
    fontes: CadeiaFontes,
    hoje: date,
    *,
    pausa_s: float = 0.0,
    dormir: Callable[[float], None] | None = None,
) -> str:
    dormir = dormir or time.sleep
    with engine.begin() as conn:
        execucao = repo.iniciar_execucao(conn, "fundamentos")
        ativos = repo.listar_ativos_ativos(conn)
    ok = erro = 0
    erros: dict[str, str] = {}
    for i, (ativo_id, ticker) in enumerate(ativos):
        if i and pausa_s:
            dormir(pausa_s)
        try:
            f = fontes.fundamentos(ticker)
            if f is None:
                continue
            with engine.begin() as conn:
                if f.dy_12m is None:
                    preco = repo.ultimo_fechamento(conn, ativo_id)
                    soma = repo.soma_proventos_12m(conn, ativo_id, hoje)
                    if preco and soma:
                        f = replace(f, dy_12m=round(float(soma / preco * Decimal(100)), 4))
                repo.upsert_fundamentos(conn, ativo_id, f)
            ok += 1
        except Exception as e:
            log.exception("falha nos fundamentos de %s", ticker)
            erro += 1
            erros[ticker] = f"{type(e).__name__}: {e}"[:500]
    status = status_por_contagem(ok, erro)
    with engine.begin() as conn:
        repo.finalizar_execucao(conn, execucao, status, ok, erro, {"erros": erros})
    return status


def token_interno(segredo: str, agora: datetime | None = None) -> str:
    agora = agora or datetime.now(UTC)
    claims = {"sub": "worker", "plano": "free", "role": "admin", "iat": agora,
              "exp": agora + timedelta(seconds=60)}  # fmt: skip
    return jwt.encode(claims, segredo, algorithm="HS256")


def revalidar_web(
    url_base: str, segredo: str, tickers: list[str], client: httpx.Client | None = None
) -> str:
    """Pede à web que renove o cache das páginas afetadas. Não altera o status do job."""
    if not url_base or not segredo:
        return "ignorada"
    tags = ["mercado", *(f"ativo:{t}" for t in tickers)]
    try:
        cli = client or httpx.Client(timeout=15)
        resp = cli.post(
            f"{url_base.rstrip('/')}/api/internal/revalidate",
            json={"tags": tags},
            headers={"Authorization": f"Bearer {token_interno(segredo)}"},
        )
        resp.raise_for_status()
        return "ok"
    except httpx.HTTPError as e:
        log.warning("revalidação falhou: %s", e)
        return f"erro: {e}"[:200]
