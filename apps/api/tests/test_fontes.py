import json
from datetime import date
from decimal import Decimal as D
from itertools import pairwise
from pathlib import Path

import httpx
import pytest

from dominio.modelos import AtivoInfo, Candle, Provento
from fontes.base import ClienteHttp, ErroFonte
from fontes.brapi import BrapiFonte
from fontes.cadeia import CadeiaFontes
from fontes.yahoo import YahooFonte

FIXTURES = Path(__file__).parent / "fixtures"


def fixture(nome: str) -> dict:
    return json.loads((FIXTURES / nome).read_text(encoding="utf-8"))


def http_com(handler) -> ClienteHttp:
    return ClienteHttp(httpx.Client(transport=httpx.MockTransport(handler)), dormir=lambda s: None)


# Yahoo


def test_yahoo_cotacoes_petr4():
    r = fixture("yahoo_petr4_2024s2.json")["chart"]["result"][0]
    candles = YahooFonte.parse_cotacoes(r, date(2024, 7, 1), date(2024, 12, 31))
    assert len(candles) == 127
    assert candles[0] == Candle(
        date(2024, 7, 1), D("38.31"), D("38.76"), D("38.18"), D("38.63"), D("29.3779"), 24963500
    )
    assert candles[-1].data == date(2024, 12, 30)
    assert all(a.data < b.data for a, b in pairwise(candles))


def test_yahoo_filtra_periodo():
    r = fixture("yahoo_petr4_2024s2.json")["chart"]["result"][0]
    candles = YahooFonte.parse_cotacoes(r, date(2024, 12, 2), date(2024, 12, 6))
    assert [c.data.day for c in candles] == [2, 3, 4, 5, 6]


def test_yahoo_proventos_usam_dia_util_anterior_a_data_ex():
    r = fixture("yahoo_petr4_2024s2.json")["chart"]["result"][0]
    proventos = YahooFonte.parse_proventos(r)
    assert proventos[0] == Provento("dividendo", date(2024, 8, 21), D("1.0532"))


def test_yahoo_grupamento_mglu3():
    r = fixture("yahoo_mglu3_grupamento.json")["chart"]["result"][0]
    assert YahooFonte.parse_proventos(r) == [Provento("grupamento", date(2024, 5, 24), D("0.1"))]


def test_yahoo_ticker_inexistente_devolve_vazio():
    corpo = fixture("yahoo_inexistente.json")
    fonte = YahooFonte(http_com(lambda req: httpx.Response(404, json=corpo)))
    assert fonte.cotacoes("XXXX9", date(2024, 1, 1), date(2024, 2, 1)) == []


def test_yahoo_monta_requisicao_com_sufixo_sa():
    pedidos = []

    def handler(req: httpx.Request):
        pedidos.append(req)
        return httpx.Response(200, json=fixture("yahoo_petr4_2024s2.json"))

    YahooFonte(http_com(handler)).cotacoes("PETR4", date(2024, 7, 1), date(2024, 12, 31))
    assert pedidos[0].url.path.endswith("/PETR4.SA")
    assert pedidos[0].url.params["interval"] == "1d"


# brapi


def test_brapi_lista_mapeia_tipos():
    ativos = BrapiFonte.parse_lista(fixture("brapi_list.json"))
    por_ticker = {a.ticker: a for a in ativos}
    assert por_ticker["FNAM11"].tipo == "etf"
    assert por_ticker["PETR4"] == AtivoInfo(
        "PETR4",
        "PETROLEO BRASILEIRO S.A. PETROBRAS",
        "acao",
        "Energy Minerals",
        "Petróleo e Gás Integrado",
        "https://icons.brapi.dev/icons/PETR4.svg",
    )


def test_brapi_lista_ignora_subtipos_fora_do_escopo():
    dados = {"stocks": [{"stock": "ABCD11", "name": "X", "type": "fund", "subType": "fidc"}]}
    assert BrapiFonte.parse_lista(dados) == []


def test_brapi_paginacao_do_catalogo():
    def handler(req: httpx.Request):
        pagina = int(req.url.params["page"])
        stocks = [{"stock": f"TST{pagina}3", "name": "T", "type": "stock", "subType": "stock"}]
        return httpx.Response(200, json={"stocks": stocks, "hasNextPage": pagina < 3})

    ativos = BrapiFonte(http_com(handler)).listar_ativos()
    assert [a.ticker for a in ativos] == ["TST13", "TST23", "TST33"]


def test_brapi_proventos_petr4():
    r = fixture("brapi_petr4.json")["results"][0]
    proventos = BrapiFonte.parse_proventos(r)
    assert (
        Provento("dividendo", date(2026, 8, 21), D("0.47156696"), date(2026, 12, 21)) in proventos
    )
    societarios = {(p.tipo, p.data_com): p.valor for p in proventos if p.societario}
    assert societarios[("desdobramento", date(2008, 4, 25))] == D(2)
    assert societarios[("grupamento", date(2000, 6, 21))] == D("0.01")
    chaves = [(p.tipo, p.data_com) for p in proventos]
    assert len(chaves) == len(set(chaves))


def test_brapi_fundamentos_petr4():
    r = fixture("brapi_petr4.json")["results"][0]
    f = BrapiFonte.parse_fundamentos(r, date(2026, 11, 24))
    assert f.pvp == pytest.approx(1.0547, abs=1e-4)
    assert f.roe == pytest.approx(27.8228)
    assert f.dy_12m == pytest.approx(8.82)
    assert f.div_liq_ebitda == pytest.approx((362505 - 62636) / 289816, abs=1e-4)
    assert f.valor_mercado == D("569288804804")


def test_brapi_cotacoes_usam_horario_de_brasilia():
    r = fixture("brapi_petr4.json")["results"][0]
    candles = BrapiFonte.parse_cotacoes(r, date(2026, 1, 1), date(2026, 12, 31))
    assert candles[0].data == date(2026, 10, 26)
    assert candles[0].fechamento == D("53.88")


def test_brapi_envia_token_no_header():
    pedidos = []

    def handler(req):
        pedidos.append(req)
        return httpx.Response(200, json={"results": []})

    BrapiFonte(http_com(handler), token="abc").proventos("PETR4")
    assert pedidos[0].headers["Authorization"] == "Bearer abc"


# HTTP e cadeia


def test_retenta_429_e_5xx_com_backoff():
    respostas = iter([httpx.Response(429), httpx.Response(503), httpx.Response(200, json={})])
    esperas = []
    cli = ClienteHttp(
        httpx.Client(transport=httpx.MockTransport(lambda req: next(respostas))),
        dormir=esperas.append,
    )
    assert cli.get_json("https://x.test/") == (200, {})
    assert esperas == [1.0, 2.0]


def test_desiste_apos_3_tentativas():
    cli = http_com(lambda req: httpx.Response(500))
    with pytest.raises(ErroFonte):
        cli.get_json("https://x.test/")


class FonteFalsa:
    def __init__(self, nome, candles=None, erro=False):
        self.nome = nome
        self.candles = candles or []
        self.erro = erro
        self.chamadas = 0

    def cotacoes(self, ticker, inicio, fim):
        self.chamadas += 1
        if self.erro:
            raise ErroFonte("fora do ar")
        return self.candles


CANDLE = Candle(date(2025, 1, 2), D(1), D(1), D(1), D(1), D(1), 1)


def test_cadeia_usa_proxima_fonte_quando_vazia_ou_com_erro():
    a, b, c = FonteFalsa("a", erro=True), FonteFalsa("b"), FonteFalsa("c", [CANDLE])
    cadeia = CadeiaFontes(cotacoes=[a, b, c], proventos=[], catalogo=[], fundamentos=[])
    assert cadeia.cotacoes("PETR4", date(2025, 1, 1), date(2025, 1, 2)) == [CANDLE]
    assert (a.chamadas, b.chamadas, c.chamadas) == (1, 1, 1)


def test_cadeia_levanta_erro_se_todas_falham():
    cadeia = CadeiaFontes(
        cotacoes=[FonteFalsa("a", erro=True), FonteFalsa("b", erro=True)],
        proventos=[],
        catalogo=[],
        fundamentos=[],
    )
    with pytest.raises(ErroFonte):
        cadeia.cotacoes("PETR4", date(2025, 1, 1), date(2025, 1, 2))


def test_sem_token_a_brapi_sai_das_cadeias_de_cotacoes_e_proventos():
    from app.config import Settings
    from fontes.cadeia import criar_cadeia

    sem = criar_cadeia(Settings(brapi_token=""))
    assert [f.nome for f in sem._proventos] == ["yahoo"]
    assert [f.nome for f in sem._cotacoes] == ["yahoo"]
    com = criar_cadeia(Settings(brapi_token="x"))
    assert [f.nome for f in com._proventos] == ["brapi", "yahoo"]
    assert [f.nome for f in com._cotacoes] == ["yahoo", "brapi"]
