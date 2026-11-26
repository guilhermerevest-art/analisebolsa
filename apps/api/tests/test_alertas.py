from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import text

from app.notificacao import Canais, InscricaoExpirada
from dominio.alertas import (
    INSIGHTS_ALERTA,
    LIMITE_WHATSAPP,
    Disparo,
    Pregao,
    Regra,
    avaliar,
    compor_push,
    compor_whatsapp,
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


def test_push_um_ou_varios():
    um = compor_push([Disparo("PETR4", D, "PETR4 fechou acima de R$ 40,00.")])
    assert um == {
        "titulo": "1 alerta disparado",
        "corpo": "PETR4 fechou acima de R$ 40,00.",
        "url": "/ativo/PETR4",
    }
    dois = compor_push([Disparo("PETR4", D, "a."), Disparo("VALE3", D, "b.")])
    assert dois == {"titulo": "2 alertas disparados", "corpo": "a. E mais 1.", "url": "/alertas"}


def test_whatsapp_numa_linha_e_cortado():
    ds = [Disparo("PETR4", D, "PETR4 fechou acima de R$ 40,00."), Disparo("VALE3", D, "VALE3\nx")]
    assert compor_whatsapp(ds) == "PETR4 fechou acima de R$ 40,00; VALE3 x"
    muitos = [Disparo("PETR4", D, "x" * 100 + ".") for _ in range(20)]
    texto = compor_whatsapp(muitos)
    assert len(texto) <= LIMITE_WHATSAPP and texto.endswith("; e mais 12")
    assert "\n" not in texto


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
    ds = [Disparo("PETR4", D, t) for t in textos if t]
    textos += [*compor_push(ds).values(), compor_whatsapp(ds)]
    assert None not in textos
    for t in textos:
        assert not PROIBIDAS.search(t), t


class PushFalso:
    def __init__(self, falhar=(), expirados=()):
        self.enviados, self.falhar, self.expirados = [], set(falhar), set(expirados)

    def enviar(self, endpoint, p256dh, auth, payload):
        if endpoint in self.expirados:
            raise InscricaoExpirada
        if endpoint in self.falhar:
            raise OSError("push fora")
        self.enviados.append((endpoint, payload["titulo"]))


class WhatsAppFalso:
    def __init__(self, falhar=()):
        self.enviados, self.falhar = [], set(falhar)

    def enviar_alertas(self, telefone, disparos, link):
        if telefone in self.falhar:
            raise OSError("whatsapp fora")
        self.enviados.append((telefone, compor_whatsapp(disparos), link))

    def tem_whatsapp(self, telefone):
        return False if telefone.endswith("99999999") else None

    def enviar_codigo(self, telefone, codigo):
        self.enviados.append((telefone, codigo))


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


def ligar_canais(db):
    with db.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO push_inscricoes (user_id, endpoint, p256dh, auth, criado_em) VALUES "
                "('u1', 'https://p/1', 'k', 'a', now() - interval '1 day'),"
                "('u1', 'https://p/velho', 'k', 'a', now() - interval '1 day'),"
                "('u2', 'https://p/2', 'k', 'a', now() - interval '1 day')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO whatsapp (user_id, telefone, confirmado_em, ativo) VALUES "
                "('u1', '5511900000001', now() - interval '1 day', true),"
                "('u2', '5511900000002', NULL, true)"
            )
        )


def canais_enviados(db):
    with db.connect() as conn:
        return conn.execute(
            text("SELECT alerta_id, canal FROM alertas_envios ORDER BY alerta_id, canal")
        ).all()


@pytest.mark.db
def test_sem_canal_configurado_guarda_os_disparos(db):
    preparar(db)
    ligar_canais(db)
    res = processar_alertas(db, Canais(), "https://s")
    assert res == {"disparados": 2, "push": "não configurado", "whatsapp": "não configurado"}
    assert canais_enviados(db) == []


@pytest.mark.db
def test_envio_por_canal_e_reenvio_do_que_falhou(db):
    preparar(db)
    ligar_canais(db)
    avaliar_alertas(db)

    push = PushFalso(falhar={"https://p/2"}, expirados={"https://p/velho"})
    wa = WhatsAppFalso(falhar={"5511900000001"})
    res = enviar_pendentes(db, Canais(push, wa), "https://s/")
    # u1 recebe push (um aparelho expirado é apagado); u2 falha no push; WhatsApp: só u1 está
    # confirmado e o envio falhou.
    assert res == {
        "push": {"enviados": 1, "falhas": 1, "pendentes": 2},
        "whatsapp": {"enviados": 0, "falhas": 1, "pendentes": 1},
    }
    assert push.enviados == [("https://p/1", "1 alerta disparado")]
    with db.connect() as conn:
        endpoints = conn.execute(text("SELECT endpoint FROM push_inscricoes ORDER BY 1")).all()
    assert [e[0] for e in endpoints] == ["https://p/1", "https://p/2"]
    assert canais_enviados(db) == [(1, "push")]

    push, wa = PushFalso(), WhatsAppFalso()
    res = processar_alertas(db, Canais(push, wa), "https://s/")
    assert res["push"] == {"enviados": 1, "falhas": 0, "pendentes": 1}
    assert push.enviados == [("https://p/2", "1 alerta disparado")]
    assert wa.enviados == [
        ("5511900000001", wa.enviados[0][1], "https://s/alertas"),
    ]
    assert "fechou acima de R$ 40,00" in wa.enviados[0][1]
    assert canais_enviados(db) == [(1, "push"), (1, "whatsapp"), (2, "push")]
    assert enviar_pendentes(db, Canais(push, wa), "https://s")["push"]["pendentes"] == 0


@pytest.mark.db
def test_whatsapp_pausado_ou_ligado_depois_nao_recebe_antigos(db):
    preparar(db)
    ligar_canais(db)
    avaliar_alertas(db)
    with db.begin() as conn:
        conn.execute(text("UPDATE whatsapp SET ativo = false WHERE user_id = 'u1'"))
        conn.execute(text("UPDATE push_inscricoes SET criado_em = now() + interval '1 day'"))
    res = enviar_pendentes(db, Canais(PushFalso(), WhatsAppFalso()), "https://s")
    assert res["push"]["pendentes"] == 0 and res["whatsapp"]["pendentes"] == 0
