from datetime import date
from decimal import Decimal as D

from dominio.modelos import Candle
from dominio.validacao import validar_candles


def c(dia: int, o, h, lo, f, vol=100, mes=3):
    return Candle(date(2025, mes, dia), D(o), D(h), D(lo), D(f), D(f), vol)


def test_aceita_candles_normais():
    validos, rejeitados, _ = validar_candles([c(3, 10, 11, 9, 10.5), c(4, 10.5, 11, 10, 10.8)])
    assert len(validos) == 2 and rejeitados == []


def test_rejeita_preco_nao_positivo_e_maxima_menor():
    _, rej, _ = validar_candles([c(3, 0, 11, 9, 10), c(4, 10, 9, 11, 10)])
    assert [r.motivo for r in rej] == ["preco_nao_positivo", "maxima_menor_que_minima"]


def test_tolerancia_de_1pct_fora_do_intervalo():
    validos, rej, _ = validar_candles([c(3, "11.20", 11, 9, 10), c(4, "11.05", 11, 9, 10)])
    assert [r.motivo for r in rej] == ["abertura_fora_do_intervalo"]
    assert [v.data.day for v in validos] == [4]


def test_pico_isolado_acima_de_50pct_e_rejeitado():
    anterior = c(3, 10, 11, 9, 10)
    validos, rej, alertas = validar_candles(
        [c(4, 25, 25, 24, 25), c(5, 10, 11, 9, 10.2)], anterior=anterior
    )
    assert [r.motivo for r in rej] == ["variacao_acima_de_50pct"]
    # a referência continua sendo o último candle aceito
    assert [v.data.day for v in validos] == [5]
    assert alertas == []


def test_salto_sem_pregao_seguinte_fica_para_a_proxima_execucao():
    _, rej, _ = validar_candles([c(4, 5, 5.5, 5, 5.3)], anterior=c(3, 12, 13, 12, 12.7))
    assert [r.motivo for r in rej] == ["variacao_acima_de_50pct"]


def test_novo_nivel_confirmado_e_aceito_com_alerta():
    # caso real: MGLU3 foi de 12,69 para 5,30 em 26/10/2026 sem evento nas fontes
    validos, rej, alertas = validar_candles(
        [c(26, 5, 5.5, 5, 5.3, mes=10), c(27, 5.3, 5.9, 5.2, 5.75, mes=10)],
        anterior=c(23, 12.7, 12.9, 12.5, 12.69, mes=10),
    )
    assert rej == []
    assert len(validos) == 2
    assert [(a.data.day, a.motivo) for a in alertas] == [(26, "salto_sem_evento")]


def test_variacao_grande_com_evento_societario_e_aceita():
    anterior = c(3, 10, 11, 9, 10)
    validos, rej, _ = validar_candles(
        [c(4, 1, 1.1, 0.9, 1)], anterior=anterior, datas_eventos=[date(2025, 3, 3)]
    )
    assert rej == [] and len(validos) == 1
