from datetime import date, timedelta

from dominio.renda_fixa import Investimento, aliquota_ir, avaliar, descrever_taxa

HOJE = date(2025, 1, 10)


def dias_uteis(inicio: date, n: int) -> list[date]:
    saida, d = [], inicio
    while len(saida) < n:
        d += timedelta(days=1)
        if d.weekday() < 5:
            saida.append(d)
    return saida


def test_aliquota_regressiva():
    assert [aliquota_ir(d) for d in (1, 180, 181, 360, 361, 720, 721)] == [
        22.5,
        22.5,
        20,
        20,
        17.5,
        17.5,
        15,
    ]


def test_cdb_pos_fixado_com_ir():
    cdi = {d: 0.05 for d in dias_uteis(date(2025, 1, 2), 3)}
    inv = Investimento("cdb", date(2025, 1, 2), 10000, "cdi", 100)
    a = avaliar(inv, HOJE, cdi, {})
    # 10.000 × 1,0005³ = 10.015,0075; ganho 15,0075 × 22,5% = 3,38.
    assert (a.bruto, a.ir, a.liquido, a.aliquota) == (10015.01, 3.38, 10011.63, 22.5)
    # 110% do CDI rende 0,055% por dia: 10.000 × 1,00055³ = 10.016,51.
    assert (
        avaliar(Investimento("cdb", date(2025, 1, 2), 10000, "cdi", 110), HOJE, cdi, {}).bruto
        == 10016.51
    )


def test_prefixado_em_252_dias_uteis_e_lci_isenta():
    calendario = dias_uteis(date(2024, 1, 2), 252)
    cdi = dict.fromkeys(calendario, 0.04)
    ate = calendario[-1]
    inv = Investimento("cdb", date(2024, 1, 2), 10000, "prefixado", 12)
    a = avaliar(inv, ate, cdi, {})
    # 252 dias úteis depois de 02/01/2024 caem em 19/12/2024: 352 dias corridos, 20% de IR.
    assert a.bruto == 11200.0 and a.aliquota == 20.0 and a.ir == 240.0 and a.liquido == 10960.0
    lci = avaliar(
        Investimento("lci_lca", date(2024, 1, 2), 10000, "prefixado", 12, isento_ir=True),
        ate,
        cdi,
        {},
    )
    assert lci.ir == 0 and lci.liquido == 11200.0 and round(lci.rendimento, 2) == 12.0


def test_ipca_mais_soma_os_meses_completos():
    ipca = {date(2024, 1, 1): 1.0, date(2024, 2, 1): 1.0, date(2024, 3, 1): 1.0}
    inv = Investimento("tesouro", date(2024, 1, 15), 1000, "ipca", 0)
    # Aplicado em janeiro: entram fevereiro e março (abril ainda não fechou em 10/04).
    a = avaliar(inv, date(2024, 4, 10), {}, ipca)
    assert a.bruto == round(1000 * 1.01 * 1.01, 2)


def test_fundo_por_cotas_da_cvm_e_resgate():
    cotas = {date(2024, 3, 4): 10.0, date(2024, 3, 5): 10.5, date(2024, 6, 3): 12.0}
    # Aplicou no sábado: vale a cota do primeiro dia útil depois.
    inv = Investimento("fundo", date(2024, 3, 2), 1000)
    a = avaliar(inv, HOJE, {}, {}, cotas)
    assert (a.cotas, a.bruto, a.data, a.ir) == (100.0, 1200.0, date(2024, 6, 3), None)
    assert round(a.rendimento, 2) == 20.0
    # Com o número de cotas informado, ele manda.
    assert (
        avaliar(Investimento("fundo", date(2024, 3, 2), 1000, cotas=50), HOJE, {}, {}, cotas).bruto
        == 600.0
    )
    antiga = avaliar(Investimento("fundo", date(2019, 5, 2), 1000), HOJE, {}, {}, cotas)
    assert antiga.bruto is None and antiga.observacao == "Informe o número de cotas"
    sem = avaliar(inv, HOJE, {}, {}, {})
    assert sem.bruto is None and "CVM" in sem.observacao
    resgatado = Investimento(
        "cdb", date(2024, 1, 2), 1000, "cdi", 100, resgate_data=date(2024, 3, 1), resgate_valor=1020
    )
    r = avaliar(resgatado, HOJE, {}, {})
    assert (r.bruto, r.ir, r.observacao) == (1020.0, 4.5, "Resgatado")


def test_descrever_taxa():
    assert descrever_taxa("cdi", 110) == "110% do CDI"
    assert descrever_taxa("prefixado", 12.5) == "12,5% ao ano"
    assert descrever_taxa("ipca", 6) == "IPCA + 6% ao ano"
