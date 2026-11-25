import time
from datetime import date
from decimal import Decimal as D

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.config import get_settings
from app.db import get_engine
from app.deps import decodificar_token
from app.erros import Problema
from app.main import create_app
from dominio.modelos import AtivoInfo, Fundamentos, Provento
from tests.conftest import serie_candles
from worker import repositorio as repo

SEGREDO = "segredo-de-teste-com-mais-de-32-bytes!!"
HOJE = date(2025, 6, 4)


def token(role="user", validade=60, segredo=SEGREDO, **extra):
    agora = int(time.time())
    claims = {"sub": "u1", "plano": "free", "role": role, "iat": agora, "exp": agora + validade}
    return jwt.encode(claims | extra, segredo, algorithm="HS256")


# JWT (sem banco)


def test_token_valido():
    u = decodificar_token(token("admin"), SEGREDO)
    assert (u.id, u.role, u.admin) == ("u1", "admin", True)


@pytest.mark.parametrize(
    ("tok", "motivo"),
    [
        (token(validade=-30), "expirado"),
        (token(validade=3600), "acima de 60 s"),
        (token(segredo="outro-segredo-com-mais-de-32-bytes!!!"), "inválido"),
        ("nao-e-jwt", "inválido"),
    ],
)
def test_token_rejeitado(tok, motivo):
    with pytest.raises(Problema) as e:
        decodificar_token(tok, SEGREDO)
    assert e.value.status == 401 and motivo in e.value.detalhe


def test_token_sem_exp_e_rejeitado():
    sem_exp = jwt.encode({"sub": "u1"}, SEGREDO, algorithm="HS256")
    with pytest.raises(Problema):
        decodificar_token(sem_exp, SEGREDO)


# Endpoints (com banco)


@pytest.fixture
def cliente(db, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", str(db.url.render_as_string(hide_password=False)))
    monkeypatch.setenv("INTERNAL_JWT_SECRET", SEGREDO)
    get_settings.cache_clear()
    get_engine.cache_clear()
    with db.begin() as conn:
        repo.sincronizar_ativos(
            conn,
            [
                AtivoInfo("PETR4", "Petroleo Brasileiro S.A. Petrobras", "acao", "Energia"),
                AtivoInfo("PETR3", "Petroleo Brasileiro S.A. Petrobras", "acao"),
                AtivoInfo("HGLG11", "CSHG Logistica", "fii"),
                AtivoInfo("VALE3", "Vale S.A.", "acao"),
            ],
        )
        ids = dict(conn.execute(text("SELECT ticker, ativo_id FROM ativos")).all())
        repo.upsert_cotacoes(conn, ids["PETR4"], serie_candles(date(2024, 1, 1), HOJE))
        repo.upsert_cotacoes(conn, ids["VALE3"], serie_candles(date(2024, 1, 1), HOJE, base=60))
        repo.upsert_proventos(
            conn,
            ids["PETR4"],
            [
                Provento("dividendo", date(2024, 5, 2), D("1.5"), date(2024, 6, 1)),
                Provento("jcp", date(2024, 11, 4), D("0.5")),
                Provento("dividendo", date(2025, 3, 3), D("1.0")),
            ],
        )
        repo.upsert_fundamentos(conn, ids["PETR4"], Fundamentos(date(2025, 6, 2), pl=4.5, pvp=1.1))
        repo.upsert_fundamentos(conn, ids["PETR4"], Fundamentos(date(2025, 5, 26), pl=4.2))
        execucao = repo.iniciar_execucao(conn, "eod")
        repo.finalizar_execucao(conn, execucao, "ok", 2, 0, {})
    with TestClient(create_app()) as c:
        yield c
    get_settings.cache_clear()
    get_engine.cache_clear()


@pytest.mark.db
def test_health(cliente):
    assert cliente.get("/v1/health").json() == {"status": "ok", "banco": "ok"}


@pytest.mark.db
def test_busca_por_prefixo_de_ticker(cliente):
    r = cliente.get("/v1/ativos", params={"busca": "petr"}).json()
    assert [a["ticker"] for a in r["itens"]] == ["PETR3", "PETR4"]
    assert r["total"] == 2


@pytest.mark.db
def test_busca_ticker_exato_vem_primeiro(cliente):
    r = cliente.get("/v1/ativos", params={"busca": "PETR4"}).json()
    assert r["itens"][0]["ticker"] == "PETR4"


@pytest.mark.db
def test_busca_por_nome_e_tipo(cliente):
    assert [a["ticker"] for a in cliente.get("/v1/ativos?busca=logistica").json()["itens"]] == [
        "HGLG11"
    ]
    r = cliente.get("/v1/ativos", params={"tipo": "fii"}).json()
    assert [a["ticker"] for a in r["itens"]] == ["HGLG11"]


@pytest.mark.db
def test_busca_paginada(cliente):
    r = cliente.get("/v1/ativos", params={"limite": 2, "pagina": 2}).json()
    assert r["total"] == 4 and len(r["itens"]) == 2


@pytest.mark.db
def test_detalhe_com_variacoes(cliente):
    r = cliente.get("/v1/ativos/petr4").json()
    assert r["ticker"] == "PETR4" and r["setor"] == "Energia"
    assert r["ultima_cotacao"]["data"] == "2025-06-04"
    assert isinstance(r["ultima_cotacao"]["fechamento"], str)
    candles = serie_candles(date(2024, 1, 1), HOJE)
    esperado = round(float((candles[-1].fechamento / candles[-2].fechamento - 1) * 100), 2)
    assert r["variacoes"]["dia"] == esperado
    assert r["variacoes"]["ano"] is not None and r["variacoes"]["doze_meses"] is not None


@pytest.mark.db
def test_ativo_sem_cotacoes(cliente):
    r = cliente.get("/v1/ativos/HGLG11").json()
    assert r["ultima_cotacao"] is None
    assert r["variacoes"] == {"dia": None, "doze_meses": None, "ano": None}


@pytest.mark.db
def test_404_em_formato_problem_json(cliente):
    r = cliente.get("/v1/ativos/XXXX3")
    assert r.status_code == 404
    assert r.headers["content-type"] == "application/problem+json"
    assert r.json()["status"] == 404 and "XXXX3" in r.json()["detail"]


@pytest.mark.db
def test_ticker_invalido_422(cliente):
    r = cliente.get("/v1/ativos/PE$R4/cotacoes")
    assert r.status_code == 422
    assert r.headers["content-type"] == "application/problem+json"


@pytest.mark.db
def test_cotacoes_diarias(cliente):
    r = cliente.get(
        "/v1/ativos/PETR4/cotacoes", params={"inicio": "2025-06-02", "fim": "2025-06-04"}
    ).json()
    assert [c["data"] for c in r["candles"]] == ["2025-06-02", "2025-06-03", "2025-06-04"]


@pytest.mark.db
def test_cotacoes_semanais_agregadas(cliente):
    r = cliente.get(
        "/v1/ativos/PETR4/cotacoes",
        params={"inicio": "2025-05-26", "fim": "2025-06-06", "periodo": "1w"},
    ).json()
    candles = serie_candles(date(2024, 1, 1), HOJE)
    semana = [c for c in candles if date(2025, 5, 26) <= c.data <= date(2025, 5, 30)]
    primeira = r["candles"][0]
    assert primeira["data"] == "2025-05-26"
    assert D(primeira["abertura"]) == semana[0].abertura
    assert D(primeira["fechamento"]) == semana[-1].fechamento
    assert D(primeira["maxima"]) == max(c.maxima for c in semana)
    assert primeira["volume"] == sum(c.volume for c in semana)
    assert len(r["candles"]) == 2  # a segunda semana vai até 04/06


@pytest.mark.db
def test_cotacoes_mensais(cliente):
    r = cliente.get(
        "/v1/ativos/PETR4/cotacoes",
        params={"inicio": "2025-01-01", "fim": "2025-06-30", "periodo": "1M"},
    ).json()
    assert [c["data"][:7] for c in r["candles"]] == [
        "2025-01", "2025-02", "2025-03", "2025-04", "2025-05", "2025-06",
    ]  # fmt: skip


@pytest.mark.db
def test_periodo_invertido_422(cliente):
    r = cliente.get(
        "/v1/ativos/PETR4/cotacoes", params={"inicio": "2025-06-04", "fim": "2025-01-01"}
    )
    assert r.status_code == 422


@pytest.mark.db
def test_fundamentos(cliente):
    r = cliente.get("/v1/ativos/PETR4/fundamentos").json()
    assert r["ultimo"]["data_referencia"] == "2025-06-02" and r["ultimo"]["pl"] == 4.5
    assert len(r["historico"]) == 2


@pytest.mark.db
def test_proventos_e_dy_por_ano(cliente):
    r = cliente.get("/v1/ativos/PETR4/proventos").json()
    assert [p["data_com"] for p in r["itens"]] == ["2025-03-03", "2024-11-04", "2024-05-02"]
    assert r["itens"][0]["valor"] == "1"
    anos = {a["ano"]: a for a in r["dy_por_ano"]}
    assert anos[2024]["total"] == "2.00"
    assert anos[2024]["dy"] is not None


@pytest.mark.db
def test_destaques(cliente):
    r = cliente.get("/v1/mercado/destaques", params={"volume_minimo": 0}).json()
    assert r["data"] == "2025-06-04"
    tickers = {d["ticker"] for d in r["altas"] + r["baixas"]}
    assert tickers <= {"PETR4", "VALE3"}


@pytest.mark.db
def test_admin_exige_token(cliente):
    assert cliente.get("/v1/admin/execucoes").status_code == 401
    r = cliente.get("/v1/admin/execucoes", headers={"Authorization": f"Bearer {token()}"})
    assert r.status_code == 403
    r = cliente.get("/v1/admin/execucoes", headers={"Authorization": f"Bearer {token('admin')}"})
    assert r.status_code == 200
    assert r.json()["itens"][0]["status"] == "ok"


@pytest.mark.db
def test_token_expirado_na_rota_publica_e_401(cliente):
    r = cliente.get("/v1/ativos", headers={"Authorization": f"Bearer {token(validade=-30)}"})
    assert r.status_code == 401
    assert r.headers["www-authenticate"] == "Bearer"


# Chave interna (API exposta na Vercel; sem banco)


@pytest.fixture
def cliente_com_chave(monkeypatch):
    monkeypatch.setenv("INTERNAL_API_KEY", "chave-de-teste")
    get_settings.cache_clear()
    yield TestClient(create_app(), raise_server_exceptions=False)
    get_settings.cache_clear()


@pytest.mark.parametrize("cabecalho", [{}, {"X-Internal-Key": "errada"}])
def test_chave_interna_ausente_ou_errada(cliente_com_chave, cabecalho):
    r = cliente_com_chave.get("/v1/ativos", headers=cabecalho)
    assert r.status_code == 401
    assert r.headers["content-type"].startswith("application/problem+json")


def test_chave_interna_nao_vale_para_health(cliente_com_chave):
    r = cliente_com_chave.get("/v1/health")
    assert r.status_code != 401


def test_chave_interna_correta_passa(cliente_com_chave):
    r = cliente_com_chave.get("/v1/nao-existe", headers={"X-Internal-Key": "chave-de-teste"})
    assert r.status_code == 404  # passou da chave sem tocar no banco


# Screener (Fase 2)


@pytest.fixture
def cliente_screener(cliente, db):
    from worker.analise import executar

    assert executar(db) == "ok"
    return cliente


@pytest.mark.db
def test_screener_lista_e_ordena(cliente_screener):
    r = cliente_screener.get("/v1/screener?ordem=-preco")
    assert r.status_code == 200
    corpo = r.json()
    assert corpo["total"] == 2  # só PETR4 e VALE3 têm cotações
    assert [i["ticker"] for i in corpo["itens"]] == ["VALE3", "PETR4"]
    item = corpo["itens"][0]
    assert isinstance(item["preco"], str)
    assert item["var_12m"] is not None
    assert item["pl"] is None

    r = cliente_screener.get("/v1/screener?ordem=ticker")
    assert [i["ticker"] for i in r.json()["itens"]] == ["PETR4", "VALE3"]


@pytest.mark.db
def test_screener_filtros(cliente_screener):
    r = cliente_screener.get("/v1/screener?preco_max=40")
    assert [i["ticker"] for i in r.json()["itens"]] == ["PETR4"]
    r = cliente_screener.get("/v1/screener?pl_min=4")  # só PETR4 tem fundamentos
    assert [i["ticker"] for i in r.json()["itens"]] == ["PETR4"]
    r = cliente_screener.get("/v1/screener?tipo=fii")
    assert r.json() == {"itens": [], "pagina": 1, "limite": 50, "total": 0}
    r = cliente_screener.get("/v1/screener?setor=Energia")
    assert [i["ticker"] for i in r.json()["itens"]] == ["PETR4"]


@pytest.mark.db
def test_screener_paginacao(cliente_screener):
    r = cliente_screener.get("/v1/screener?limite=1&pagina=2&ordem=ticker")
    corpo = r.json()
    assert corpo["total"] == 2
    assert [i["ticker"] for i in corpo["itens"]] == ["VALE3"]
    r = cliente_screener.get("/v1/screener?limite=1&pagina=9")
    assert r.json()["itens"] == [] and r.json()["total"] == 2


@pytest.mark.db
@pytest.mark.parametrize(
    "consulta", ["foo=1", "ordem=drop", "ordem=-nome", "limite=101", "pl_min=abc", "tipo=x"]
)
def test_screener_rejeita_parametros_fora_da_lista(cliente_screener, consulta):
    r = cliente_screener.get(f"/v1/screener?{consulta}")
    assert r.status_code == 422


@pytest.mark.db
def test_screener_campos(cliente_screener):
    corpo = cliente_screener.get("/v1/screener/campos").json()
    nomes = [c["campo"] for c in corpo["campos"]]
    assert "dy_12m" in nomes and "rsi14" in nomes
    preco = next(c for c in corpo["campos"] if c["campo"] == "preco")
    assert preco["unidade"] == "brl" and preco["min"] < preco["max"]
    assert corpo["setores"] == ["Energia"]
    assert corpo["tipos"] == ["acao", "fii", "etf", "bdr"]


@pytest.mark.db
def test_analise_do_ativo(cliente_screener):
    r = cliente_screener.get("/v1/ativos/PETR4/analise")
    assert r.status_code == 200
    corpo = r.json()
    assert corpo["ticker"] == "PETR4"
    assert corpo["metricas"]["preco"] is not None
    assert isinstance(corpo["elegivel"], bool)
    if not corpo["elegivel"]:
        assert corpo["motivo"]
    for i in corpo["insights"]:
        assert {"codigo", "categoria", "tom", "titulo", "texto", "data"} <= i.keys()
    assert "cenario" in corpo
    if not corpo["elegivel"]:
        assert corpo["cenario"] is None


@pytest.mark.db
def test_analise_sem_calculo_e_ativo_inexistente(cliente):
    r = cliente.get("/v1/ativos/PETR4/analise")
    assert r.status_code == 200
    assert r.json()["elegivel"] is False and r.json()["insights"] == []
    assert cliente.get("/v1/ativos/XXXX3/analise").status_code == 404
