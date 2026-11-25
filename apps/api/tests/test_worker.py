from datetime import date, timedelta
from decimal import Decimal as D

import httpx
import jwt
import pytest
from sqlalchemy import text

from app.config import Settings
from dominio.modelos import AtivoInfo, Candle, Fundamentos, Provento
from fontes.base import ErroFonte
from tests.conftest import serie_candles
from worker import repositorio as repo
from worker.backfill import executar_backfill
from worker.eod import executar_eod
from worker.processamento import atualizar_fundamentos, revalidar_web

pytestmark = pytest.mark.db

HOJE = date(2025, 6, 4)  # quarta-feira
SETTINGS = Settings(pausa_entre_tickers_s=0, web_internal_url="", internal_jwt_secret="")


class FontesFalsas:
    """Implementa a interface de CadeiaFontes com dados em memória."""

    def __init__(self, catalogo, candles, proventos=None, fundamentos=None, falham=()):
        self.catalogo = catalogo
        self.candles = candles
        self._proventos = proventos or {}
        self._fundamentos = fundamentos or {}
        self.falham = set(falham)
        self.pedidos_cotacoes: list[tuple[str, date, date]] = []

    def listar_ativos(self):
        return self.catalogo

    def cotacoes(self, ticker, inicio, fim):
        self.pedidos_cotacoes.append((ticker, inicio, fim))
        if ticker in self.falham:
            raise ErroFonte("todas as fontes falharam")
        return [c for c in self.candles.get(ticker, []) if inicio <= c.data <= fim]

    def proventos(self, ticker):
        return self._proventos.get(ticker, [])

    def fundamentos(self, ticker):
        return self._fundamentos.get(ticker)


CATALOGO = [AtivoInfo("PETR4", "Petrobras", "acao"), AtivoInfo("HGLG11", "CSHG Log", "fii")]


def contar(db, tabela: str) -> int:
    with db.connect() as conn:
        return conn.execute(text(f"SELECT count(*) FROM {tabela}")).scalar_one()


def execucoes(db, tipo: str | None = None) -> list:
    sql = "SELECT tipo, status, ativos_ok, ativos_erro, detalhes FROM execucoes_job"
    with db.connect() as conn:
        linhas = conn.execute(text(sql + " ORDER BY execucao_id")).all()
    return [e for e in linhas if tipo is None or e.tipo == tipo]


def fontes_padrao(**kw):
    candles = {
        "PETR4": serie_candles(date(2024, 1, 1), HOJE),
        "HGLG11": serie_candles(date(2024, 1, 1), HOJE, base=160),
    }
    return FontesFalsas(CATALOGO, candles, **kw)


def test_eod_duas_vezes_nao_duplica(db):
    fontes = fontes_padrao(proventos={"PETR4": [Provento("dividendo", date(2025, 3, 3), D("1.2"))]})
    assert executar_eod(db, fontes, SETTINGS, HOJE) == "ok"
    cotacoes, indicadores = contar(db, "cotacoes_diarias"), contar(db, "indicadores_diarios")
    assert cotacoes == 2 * len(serie_candles(date(2024, 1, 1), HOJE))
    assert indicadores == cotacoes

    assert executar_eod(db, fontes, SETTINGS, HOJE) == "ok"
    assert contar(db, "cotacoes_diarias") == cotacoes
    assert contar(db, "indicadores_diarios") == indicadores
    assert contar(db, "proventos") == 1
    tipos = [(e.tipo, e.status, e.ativos_ok) for e in execucoes(db)]
    # catálogo e fundamentos rodam na primeira vez porque a tabela estava vazia
    assert tipos == [
        ("catalogo", "ok", 2),
        ("eod", "ok", 2),
        ("fundamentos", "ok", 0),
        ("analise", "ok", 2),
        ("eod", "ok", 2),
    ]
    # a segunda rodada não tem pregão novo, então não recalcula a análise
    assert contar(db, "metricas_ativo") == 2


def test_preenche_pregoes_faltantes_e_indicadores_incrementais(db):
    fontes = fontes_padrao()
    executar_eod(db, fontes, SETTINGS, date(2025, 5, 28))
    with db.connect() as conn:
        mm200_antes = conn.execute(
            text(
                "SELECT mm200 FROM indicadores_diarios i JOIN ativos USING (ativo_id) "
                "WHERE ticker='PETR4' AND data='2025-05-28'"
            )
        ).scalar_one()
    fontes.pedidos_cotacoes.clear()
    executar_eod(db, fontes, SETTINGS, HOJE)
    # busca a partir do último pregão gravado (inclusive), não do histórico todo
    assert ("PETR4", date(2025, 5, 28), HOJE) in fontes.pedidos_cotacoes
    with db.connect() as conn:
        ultima = conn.execute(
            text(
                "SELECT max(data) FROM indicadores_diarios i JOIN ativos USING (ativo_id) "
                "WHERE ticker='PETR4'"
            )
        ).scalar_one()
        mm200 = conn.execute(
            text(
                "SELECT mm200 FROM indicadores_diarios i JOIN ativos USING (ativo_id) "
                "WHERE ticker='PETR4' AND data=:d"
            ),
            {"d": HOJE},
        ).scalar_one()
    assert ultima == HOJE
    assert mm200 is not None and mm200_antes is not None
    closes = [float(c.fechamento) for c in fontes.candles["PETR4"]][-200:]
    assert mm200 == pytest.approx(sum(closes) / 200)


def test_status_parcial_quando_um_ticker_falha(db):
    fontes = fontes_padrao(falham={"HGLG11"})
    assert executar_eod(db, fontes, SETTINGS, HOJE) == "parcial"
    eod = execucoes(db, "eod")[-1]
    assert (eod.tipo, eod.ativos_ok, eod.ativos_erro) == ("eod", 1, 1)
    assert "HGLG11" in eod.detalhes["erros"]


def test_status_erro_quando_todos_falham(db):
    fontes = fontes_padrao(falham={"HGLG11", "PETR4"})
    assert executar_eod(db, fontes, SETTINGS, HOJE) == "erro"


def test_feriado_sem_pregao_novo_nao_altera_nada(db):
    fontes = fontes_padrao()
    executar_eod(db, fontes, SETTINGS, HOJE)
    antes = contar(db, "cotacoes_diarias")
    assert executar_eod(db, fontes, SETTINGS, HOJE + timedelta(days=1)) == "ok"
    assert contar(db, "cotacoes_diarias") == antes
    assert execucoes(db, "eod")[-1].detalhes["atualizados"] == 0


def test_linhas_invalidas_sao_rejeitadas_e_registradas(db):
    fontes = fontes_padrao()
    ruim = Candle(date(2025, 6, 5), D(30), D(29), D(31), D(30), D(30), 10)
    fontes.candles["PETR4"].append(ruim)
    executar_eod(db, fontes, SETTINGS, date(2025, 6, 5))
    eod = execucoes(db, "eod")[-1]
    assert eod.detalhes["rejeitadas"]["PETR4"] == [
        {"data": "2025-06-05", "motivo": "maxima_menor_que_minima"}
    ]


def test_catalogo_desativa_tickers_que_sumiram(db):
    executar_eod(db, fontes_padrao(), SETTINGS, HOJE)
    fontes = fontes_padrao()
    fontes.catalogo = [CATALOGO[0]]
    executar_eod(db, fontes, SETTINGS, date(2025, 6, 9), forcar_catalogo=True)
    with db.connect() as conn:
        ativos = dict(conn.execute(text("SELECT ticker, ativo FROM ativos")).all())
    assert ativos == {"PETR4": True, "HGLG11": False}


def test_provento_novo_rebaixa_historico_completo(db):
    fontes = fontes_padrao()
    executar_eod(db, fontes, SETTINGS, HOJE)
    fontes._proventos = {"PETR4": [Provento("jcp", date(2025, 6, 2), D("0.5"))]}
    fontes.pedidos_cotacoes.clear()
    executar_eod(db, fontes, SETTINGS, HOJE)
    pedidos = {t: inicio for t, inicio, _ in fontes.pedidos_cotacoes}
    assert pedidos["PETR4"] == date(2005, 1, 1)
    assert pedidos["HGLG11"] == HOJE


def test_backfill_retomavel_pula_quem_tem_historico(db):
    fontes = fontes_padrao()
    assert executar_backfill(db, fontes, SETTINGS, HOJE, tickers=["PETR4"]) == "ok"
    fontes.pedidos_cotacoes.clear()
    assert executar_backfill(db, fontes, SETTINGS, HOJE, desde=date(2024, 1, 1)) == "ok"
    assert [t for t, *_ in fontes.pedidos_cotacoes] == ["HGLG11"]
    assert execucoes(db, "backfill")[-1].detalhes["pulados"] == 1


def test_fundamentos_calculam_dy_quando_a_fonte_nao_informa(db):
    fontes = fontes_padrao(
        proventos={"PETR4": [Provento("dividendo", date(2025, 3, 3), D("2"))]},
        fundamentos={"PETR4": Fundamentos(HOJE, pl=5.0)},
    )
    executar_eod(db, fontes, SETTINGS, HOJE)
    assert atualizar_fundamentos(db, fontes, HOJE) == "ok"
    with db.connect() as conn:
        a = conn.execute(text("SELECT ativo_id FROM ativos WHERE ticker='PETR4'")).scalar_one()
        dy = conn.execute(text("SELECT dy_12m FROM fundamentos WHERE ativo_id=:a"), {"a": a})
        preco = repo.ultimo_fechamento(conn, a)
    assert dy.scalar_one() == pytest.approx(round(2 / float(preco) * 100, 4))


def test_revalidacao_envia_jwt_interno_valido():
    pedidos = []

    def handler(req: httpx.Request):
        pedidos.append(req)
        return httpx.Response(200, json={"ok": True})

    cli = httpx.Client(transport=httpx.MockTransport(handler))
    segredo = "s" * 32
    assert revalidar_web("http://web:3000", segredo, ["PETR4"], client=cli) == "ok"
    token = pedidos[0].headers["Authorization"].removeprefix("Bearer ")
    claims = jwt.decode(token, segredo, algorithms=["HS256"])
    assert claims["exp"] - claims["iat"] <= 60
    assert pedidos[0].url.path == "/api/internal/revalidate"
    assert b"ativo:PETR4" in pedidos[0].content


def test_revalidacao_ignorada_sem_configuracao():
    assert revalidar_web("", "", ["PETR4"]) == "ignorada"


def test_analise_grava_metricas_e_pode_ser_refeita(db):
    from worker.analise import executar as executar_analise

    assert executar_eod(db, fontes_padrao(), SETTINGS, HOJE) == "ok"
    with db.connect() as conn:
        m = (
            conn.execute(
                text(
                    "SELECT a.ticker, m.* FROM metricas_ativo m JOIN ativos a USING (ativo_id) "
                    "WHERE a.ticker = 'PETR4'"
                )
            )
            .mappings()
            .one()
        )
    assert m["data"] == HOJE
    assert m["pregoes"] == len(serie_candles(date(2024, 1, 1), HOJE))
    assert m["var_12m"] is not None and m["rsi14"] is not None
    assert m["tendencia"] in {"alta", "baixa", "lateral"}
    assert m["volume_financeiro_20d"] > 0

    assert executar_analise(db, ["PETR4"]) == "ok"
    assert contar(db, "metricas_ativo") == 2
    assert execucoes(db, "analise")[-1].ativos_ok == 1


def test_analise_grava_insights_e_substitui(db):
    assert executar_eod(db, fontes_padrao(), SETTINGS, HOJE) == "ok"
    with db.connect() as conn:
        linhas = conn.execute(
            text(
                "SELECT a.ticker, i.codigo, i.texto, i.data FROM insights i "
                "JOIN ativos a USING (ativo_id)"
            )
        ).all()
    # HGLG11 (R$ 160 × ~1.300 cotas/dia) passa no mínimo de liquidez e ganha a leitura de
    # tendência; PETR4 (R$ 20) fica abaixo de R$ 100 mil/dia e não recebe insights técnicos
    tickers = {t for t, *_ in linhas}
    assert ("HGLG11", "tendencia") in {(t, c) for t, c, *_ in linhas}
    assert "PETR4" not in tickers
    assert all(d == HOJE for *_, d in linhas)
    from worker.analise import executar as executar_analise

    assert executar_analise(db, ["PETR4"]) == "ok"
    assert contar(db, "insights") == len(linhas)
