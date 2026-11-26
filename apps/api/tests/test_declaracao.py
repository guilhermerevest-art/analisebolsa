from datetime import date
from decimal import Decimal as D

import pytest
from sqlalchemy import text

from dominio.carteira import Operacao
from dominio.declaracao import montar
from dominio.modelos import Provento
from tests.test_api import cliente, token  # noqa: F401 (fixture)
from tests.test_api_carteira import api, auth, lancar, nova_carteira  # noqa: F401
from worker import repositorio as repo

CADASTRO = {
    "PETR4": ("Petrobras", "acao"),
    "HGLG11": ("CSHG Logística", "fii"),
    "BOVA11": ("iShares Ibovespa", "etf"),
}


def test_bens_e_direitos_em_31_12_dos_dois_anos():
    ops = [
        Operacao(1, "PETR4", "compra", date(2024, 5, 2), D(100), D(30), D(10)),
        Operacao(2, "PETR4", "compra", date(2025, 3, 3), D(100), D(40), D(10)),
        Operacao(3, "HGLG11", "compra", date(2024, 6, 3), D(10), D(160), D(0)),
        Operacao(4, "HGLG11", "venda", date(2025, 8, 4), D(10), D(170), D(0)),
        Operacao(5, "BOVA11", "compra", date(2026, 1, 5), D(5), D(130), D(0)),  # depois
    ]
    d = montar(ops, {"PETR4": [Provento("desdobramento", date(2025, 6, 2), D(2))]}, CADASTRO, 2025)
    hglg, petr = d.bens
    assert (petr.quantidade_anterior, petr.custo_anterior) == (100, D("3010.00"))
    # Desdobramento 1:2 dobra a quantidade e mantém o custo: 400 ações, custo 7.020.
    assert (petr.quantidade, petr.custo) == (400, D("7020.00"))
    assert (petr.grupo, petr.codigo) == ("03", "01")
    assert petr.discriminacao == (
        "400 ações de Petrobras (PETR4), negociadas na B3, preço médio de R$ 17,55. "
        "Custo total de aquisição: R$ 7.020,00."
    )
    assert (hglg.quantidade_anterior, hglg.quantidade, hglg.custo) == (10, 0, 0)
    assert hglg.codigo == "03" and "vendidas em 2025" in hglg.discriminacao
    assert all(b.ticker != "BOVA11" for b in d.bens)


def test_proventos_pelo_ano_do_pagamento():
    ops = [
        Operacao(1, "PETR4", "compra", date(2024, 5, 2), D(100), D(30), D(0)),
        Operacao(2, "HGLG11", "compra", date(2024, 6, 3), D(10), D(160), D(0)),
    ]
    proventos = {
        "PETR4": [
            Provento("dividendo", date(2024, 12, 20), D("0.50"), date(2025, 1, 15)),  # conta 2025
            Provento("jcp", date(2025, 6, 10), D("1.00"), date(2025, 7, 1)),
            Provento("dividendo", date(2025, 11, 20), D("0.30"), date(2026, 2, 1)),  # 2026
        ],
        "HGLG11": [Provento("rendimento", date(2025, 3, 31), D("1.10"), None)],  # sem pagamento
    }
    d = montar(ops, proventos, CADASTRO, 2025)
    assert [(r.ticker, r.bruto) for r in d.dividendos] == [("PETR4", D("50.00"))]
    assert [(r.ticker, r.bruto) for r in d.rendimentos_fii] == [("HGLG11", D("11.00"))]
    (jcp,) = d.jcp
    assert (jcp.bruto, jcp.ir, jcp.liquido) == (D("100.00"), D("15.00"), D("85.00"))


@pytest.mark.db
def test_api_declaracao(api, db):  # noqa: F811
    cid = nova_carteira(api)
    lancar(api, cid, data="2025-01-06", quantidade="1000", preco="30")
    lancar(api, cid, tipo="venda", data="2025-03-03", quantidade="500", preco="35")  # isento
    with db.begin() as conn:
        aid = conn.execute(text("SELECT ativo_id FROM ativos WHERE ticker = 'PETR4'")).scalar()
        repo.upsert_proventos(
            conn, aid, [Provento("dividendo", date(2025, 4, 1), D("0.20"), date(2025, 4, 20))]
        )
    url = f"/v1/carteiras/{cid}/declaracao"
    assert api.get(url, headers=auth("u2")).status_code == 404
    assert api.get(f"{url}?ano=1990", headers=auth()).status_code == 422
    r = api.get(f"{url}?ano=2025", headers=auth())
    assert r.status_code == 200 and r.headers["cache-control"] == "private, no-store"
    d = r.json()
    assert d["ano"] == 2025 and d["anos"][-1] == 2025
    (bem,) = d["bens"]
    assert bem["quantidade_anterior"] == "0" and bem["quantidade"] == "500"
    assert bem["custo"] == "15000.00"
    # 0,20 × 500 = 100,00, mais o dividendo de 1,00 da fixture (data-com 03/03/2025, sem
    # pagamento conhecido) sobre as 500 que sobraram depois da venda do dia: 600,00.
    assert d["dividendos"] == [
        {
            "ticker": "PETR4",
            "nome": bem["nome"],
            "bruto": "600.00",
            "ir": "0.00",
            "liquido": "600.00",
        }
    ]
    assert d["ganho_isento_acoes"] == "2500.00" and d["darfs"] == "0.00"
    assert d["meses_com_venda"] == 1

    # Sem ano: o anterior ao atual, mas nunca antes da primeira operação.
    padrao = api.get(url, headers=auth()).json()["ano"]
    assert padrao == max(date.today().year - 1, 2025)
