import base64
import io
from datetime import date, datetime
from decimal import Decimal

import pytest
from openpyxl import Workbook

from dominio.importacao_b3 import PlanilhaInvalida, ler_negociacao, normalizar_ticker
from tests.test_api import cliente, token  # noqa: F401 (fixture)
from tests.test_api_carteira import api, auth, lancar, nova_carteira  # noqa: F401

CABECALHO = (
    "Data do Negócio",
    "Tipo de Movimentação",
    "Mercado",
    "Prazo/Vencimento",
    "Instituição",
    "Código de Negociação",
    "Quantidade",
    "Preço",
    "Valor",
)


def planilha(linhas, cabecalho=CABECALHO, antes=()) -> bytes:
    livro = Workbook()
    folha = livro.active
    for extra in antes:
        folha.append(extra)
    folha.append(cabecalho)
    for linha in linhas:
        folha.append(linha)
    saida = io.BytesIO()
    livro.save(saida)
    return saida.getvalue()


def op(data, tipo, ticker, qtd, preco, mercado="Mercado à Vista"):
    return (data, tipo, mercado, "-", "CORRETORA X", ticker, qtd, preco, None)


def test_normalizar_ticker():
    assert normalizar_ticker(" petr4f ") == "PETR4"
    assert normalizar_ticker("TAEE11F") == "TAEE11"
    assert normalizar_ticker("HGLG11") == "HGLG11"
    assert normalizar_ticker("B3SA3F") == "B3SA3"
    assert normalizar_ticker("PETRF") is None
    assert normalizar_ticker("PETRA400") is None  # opção


def test_le_o_extrato_da_b3():
    conteudo = planilha(
        [
            op("02/01/2026", "Compra", "PETR4", 100, 38.5),
            op(datetime(2026, 1, 5), "Compra", "PETR4F", 7, "38,63", "Mercado Fracionário"),
            op("06/01/2026", "Venda", "VALE3", "1.000", "R$ 61,20"),
            op("07/01/2026", "Compra", "PETRA400", 100, 0.5, "Opção de Compra"),
            op("31/02/2026", "Compra", "PETR4", 1, 1),
            op("08/01/2026", "Doação", "PETR4", 1, 1),
            op("09/01/2026", "Compra", "PETR4", 0, 1),
            (None,) * 9,  # linha vazia é pulada
        ],
        antes=[("Extrato de negociação",), ()],
    )
    linhas = ler_negociacao(conteudo)
    assert [ln.linha for ln in linhas] == [4, 5, 6, 7, 8, 9, 10]
    a, b, c, d, e, f, g = linhas
    assert (a.data, a.tipo, a.ticker, a.quantidade, a.preco, a.erro) == (
        date(2026, 1, 2),
        "compra",
        "PETR4",
        Decimal(100),
        Decimal("38.5"),
        None,
    )
    assert (b.ticker, b.quantidade, b.preco, b.data) == (
        "PETR4",
        7,
        Decimal("38.63"),
        date(2026, 1, 5),
    )
    assert (c.tipo, c.quantidade, c.preco) == ("venda", Decimal(1000), Decimal("61.20"))
    assert "Opção de Compra" in d.erro
    assert e.erro == "data inválida"
    assert "tipo de movimentação" in f.erro
    assert g.erro == "quantidade inválida"


def test_planilha_que_nao_e_da_b3():
    with pytest.raises(PlanilhaInvalida, match="colunas"):
        ler_negociacao(planilha([("a", "b")], cabecalho=("Nome", "Valor")))
    with pytest.raises(PlanilhaInvalida, match="xlsx"):
        ler_negociacao(b"isto nao e uma planilha")
    from dominio import importacao_b3

    importacao_b3.MAX_LINHAS = 3
    try:
        with pytest.raises(PlanilhaInvalida, match="passa de 3 linhas"):
            ler_negociacao(planilha([op("02/01/2026", "Compra", "PETR4", 1, 1)] * 30))
    finally:
        importacao_b3.MAX_LINHAS = 5000
    with pytest.raises(PlanilhaInvalida, match="não tem operações"):
        ler_negociacao(planilha([]))


def b64(conteudo: bytes) -> dict:
    return {"arquivo": base64.b64encode(conteudo).decode()}


@pytest.mark.db
def test_previa_e_importacao(api):  # noqa: F811
    cid = nova_carteira(api)
    lancar(api, cid, data="2026-01-02", quantidade="100", preco="38.5")  # já lançada
    conteudo = planilha(
        [
            op("02/01/2026", "Compra", "PETR4", 100, 38.5),  # duplicada
            op("02/01/2026", "Compra", "PETR4", 100, 38.5),  # igual, mas é outra execução
            op("05/01/2026", "Compra", "VALE3F", 10, 61.2, "Mercado Fracionário"),
            op("06/01/2026", "Venda", "PETR4", 50, 40),
            op("06/01/2026", "Compra", "ZZZZ3", 1, 1),  # fora do catálogo
            op("01/01/2099", "Compra", "PETR4", 1, 1),  # futuro
        ]
    )
    url = f"/v1/carteiras/{cid}/importacao"
    assert api.post(f"{url}/previa", json=b64(conteudo), headers=auth("u2")).status_code == 404

    r = api.post(f"{url}/previa", json=b64(conteudo), headers=auth())
    assert r.status_code == 200, r.text
    previa = r.json()
    assert (previa["novas"], previa["duplicadas"], previa["ignoradas"]) == (3, 1, 2)
    assert [ln["situacao"] for ln in previa["linhas"]] == [
        "duplicada",
        "nova",
        "nova",
        "nova",
        "ignorada",
        "ignorada",
    ]
    assert previa["linhas"][2]["ticker"] == "VALE3" and previa["linhas"][2]["preco"] == "61.20"
    assert "catálogo" in previa["linhas"][4]["motivo"]
    assert api.get(f"/v1/carteiras/{cid}/operacoes", headers=auth()).json()["itens"].__len__() == 1

    r = api.post(url, json=b64(conteudo), headers=auth())
    assert r.json() == {"importadas": 3, "duplicadas": 1, "ignoradas": 2}
    assert len(api.get(f"/v1/carteiras/{cid}/operacoes", headers=auth()).json()["itens"]) == 4

    # Reimportar o mesmo arquivo não duplica nada.
    previa = api.post(f"{url}/previa", json=b64(conteudo), headers=auth()).json()
    assert (previa["novas"], previa["duplicadas"]) == (0, 4)
    r = api.post(url, json=b64(conteudo), headers=auth())
    assert r.status_code == 422 and "nenhuma operação nova" in r.json()["detail"]


@pytest.mark.db
def test_importacao_com_venda_acima_da_posicao_nao_grava_nada(api):  # noqa: F811
    cid = nova_carteira(api)
    conteudo = planilha(
        [op("02/01/2026", "Compra", "PETR4", 10, 38), op("05/01/2026", "Venda", "PETR4", 50, 40)]
    )
    r = api.post(f"/v1/carteiras/{cid}/importacao", json=b64(conteudo), headers=auth())
    assert r.status_code == 422
    assert "venda de 50 PETR4" in r.json()["detail"] and "Nada foi importado" in r.json()["detail"]
    assert api.get(f"/v1/carteiras/{cid}/operacoes", headers=auth()).json()["itens"] == []


@pytest.mark.db
def test_importacao_arquivo_invalido_e_limite(api, monkeypatch):  # noqa: F811
    from app import carteira

    cid = nova_carteira(api)
    url = f"/v1/carteiras/{cid}/importacao"
    assert api.post(url, json={"arquivo": "@@@"}, headers=auth()).status_code == 422
    r = api.post(url, json=b64(b"nao e xlsx"), headers=auth())
    assert r.status_code == 422 and "xlsx" in r.json()["detail"]

    monkeypatch.setattr(carteira, "LIMITE_OPERACOES", 1)
    conteudo = planilha([op("02/01/2026", "Compra", "PETR4", 1, 1)] * 2)
    assert api.post(url, json=b64(conteudo), headers=auth()).status_code == 409
