from datetime import date
from decimal import Decimal
from html import escape

import pytest
from sqlalchemy import text

from dominio.alertas import (
    AVISO_EMAIL,
    INSIGHTS_ALERTA,
    Disparo,
    Pregao,
    Regra,
    avaliar,
    compor_email,
    descrever,
)
from dominio.modelos import AtivoInfo, Candle
from tests.test_insights import PROIBIDAS
from worker import repositorio as repo
from worker.alertas import avaliar_alertas, enviar_pendentes, processar_alertas

D = date(2026, 11, 25)


def p(fech, ant=None, insights=()):
    return Pregao(D, fech, ant, frozenset(insights))


def test_preco_acima_dispara_so_no_cruzamento():
    r = Regra("PETR4", "preco_acima", 40)
    assert avaliar(r, p(41, 39)) == "PETR4 fechou acima de R$ 40,00 em 25/11/2026, a R$ 41,00."
    assert avaliar(r, p(41, None)) is not None
    assert avaliar(r, p(41, 40.5)) is None  # já estava acima
    assert avaliar(r, p(39, 38)) is None


def test_preco_abaixo_dispara_so_no_cruzamento():
    r = Regra("VALE3", "preco_abaixo", 60)
    assert "fechou abaixo de R$ 60,00" in avaliar(r, p(59.5, 61))
    assert avaliar(r, p(59.5, 59.9)) is None
    assert avaliar(r, p(61, 62)) is None


def test_variacao_do_dia_em_modulo():
    r = Regra("PETR4", "variacao_dia", 5)
    assert avaliar(r, p(106, 100)) == (
        "PETR4 variou +6,00% no pregão de 25/11/2026, mais que os 5,00% do alerta."
    )
    assert "variou −6,00%" in avaliar(r, p(94, 100))
    assert avaliar(r, p(104, 100)) is None
    assert avaliar(r, p(104, None)) is None


def test_insight_do_dia():
    r = Regra("PETR4", "insight", codigo="maxima_52s")
    assert avaliar(r, p(10, 9, {"maxima_52s"})) == (
        "PETR4 renovou a máxima de 52 semanas no pregão de 25/11/2026."
    )
    assert avaliar(r, p(10, 9, {"volume_anormal"})) is None


def test_email_agrupado_com_links():
    ds = [Disparo("PETR4", D, "PETR4 fechou acima de R$ 40,00."), Disparo("VALE3", D, "VALE3 <x>")]
    assunto, corpo, html = compor_email(ds, "https://site.com/")
    assert assunto == "analisebolsa: 2 alertas disparados"
    assert "https://site.com/ativo/PETR4" in corpo and "https://site.com/alertas" in corpo
    assert "VALE3 &lt;x&gt;" in html and "<x>" not in html
    assert compor_email(ds[:1], "https://s")[0] == "analisebolsa: PETR4 fechou acima de R$ 40,00"


def test_textos_sem_linguagem_de_recomendacao():
    textos = []
    pregao = p(200, 1, set(INSIGHTS_ALERTA))
    for regra in [
        Regra("PETR4", "preco_acima", 40),
        Regra("PETR4", "preco_abaixo", 400),
        Regra("PETR4", "variacao_dia", 5),
        *[Regra("PETR4", "insight", codigo=c) for c in INSIGHTS_ALERTA],
    ]:
        textos += [
            descrever(regra),
            avaliar(regra, pregao if regra.tipo != "preco_abaixo" else p(1, 500)),
        ]
    # O aviso padrão ("Não é recomendação...") é o único uso permitido da palavra.
    email = compor_email([Disparo("PETR4", D, "x")], "https://s")
    textos += [t.replace(AVISO_EMAIL, "").replace(escape(AVISO_EMAIL), "") for t in email]
    assert None not in textos
    for t in textos:
        assert not PROIBIDAS.search(t), t


class EnviadorFalso:
    def __init__(self, falhar_para=()):
        self.enviados, self.falhar_para = [], set(falhar_para)

    def enviar(self, para, assunto, texto, html):
        if para in self.falhar_para:
            raise OSError("smtp fora")
        self.enviados.append((para, assunto))


def preparar(db):
    hoje = date.today()
    with db.begin() as conn:
        repo.sincronizar_ativos(conn, [AtivoInfo("PETR4", "Petrobras", "acao")])
        aid = conn.execute(text("SELECT ativo_id FROM ativos")).scalar()
        repo.upsert_cotacoes(
            conn,
            aid,
            [
                Candle(date(2026, 1, 2), *[Decimal("39")] * 5, 100),
                Candle(hoje, *[Decimal("41")] * 5, 100),
            ],
        )
        conn.execute(
            text("INSERT INTO users (id, email) VALUES ('u1','a@x.com'), ('u2','b@x.com')")
        )
        conn.execute(
            text(
                "INSERT INTO alertas (user_id, ativo_id, tipo, parametro) VALUES "
                "('u1', :a, 'preco_acima', 40), ('u2', :a, 'variacao_dia', 2),"
                "('u2', :a, 'preco_abaixo', 10)"
            ),
            {"a": aid},
        )


@pytest.mark.db
def test_avalia_grava_e_nao_repete(db):
    preparar(db)
    assert avaliar_alertas(db) == 2
    assert avaliar_alertas(db) == 0  # mesmo pregão
    with db.connect() as conn:
        textos = conn.execute(text("SELECT texto FROM alertas_disparos ORDER BY alerta_id")).all()
    assert "fechou acima de R$ 40,00" in textos[0][0] and "variou +5,13%" in textos[1][0]


@pytest.mark.db
def test_envio_um_email_por_usuario_e_reenvio_do_que_falhou(db):
    preparar(db)
    avaliar_alertas(db)
    assert enviar_pendentes(db, None, "https://s")["pendentes"] == 2  # sem SMTP: guarda

    falso = EnviadorFalso(falhar_para={"b@x.com"})
    res = enviar_pendentes(db, falso, "https://s")
    assert res == {"enviados": 1, "falhas": 1, "pendentes": 2}
    assert falso.enviados[0][0] == "a@x.com"

    falso = EnviadorFalso()
    assert processar_alertas(db, falso, "https://s") == {
        "disparados": 0,
        "enviados": 1,
        "falhas": 0,
        "pendentes": 1,
    }
    assert [e[0] for e in falso.enviados] == ["b@x.com"]
    assert enviar_pendentes(db, falso, "https://s") == {"enviados": 0, "pendentes": 0}
