"""Validação de candles antes da gravação (seção 4, etapa 3 da spec)."""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from dominio.modelos import Candle

TOLERANCIA_INTERVALO = Decimal("0.01")
VARIACAO_MAXIMA = Decimal("0.50")
JANELA_EVENTO = timedelta(days=5)


@dataclass(frozen=True, slots=True)
class Rejeicao:
    data: date
    motivo: str

    def como_dict(self) -> dict:
        return {"data": self.data.isoformat(), "motivo": self.motivo}


def _motivo_estrutural(c: Candle) -> str | None:
    precos = (c.abertura, c.maxima, c.minima, c.fechamento, c.fechamento_ajustado)
    if any(p <= 0 for p in precos):
        return "preco_nao_positivo"
    if c.volume < 0:
        return "volume_negativo"
    if c.maxima < c.minima:
        return "maxima_menor_que_minima"
    piso = c.minima * (1 - TOLERANCIA_INTERVALO)
    teto = c.maxima * (1 + TOLERANCIA_INTERVALO)
    if not piso <= c.abertura <= teto:
        return "abertura_fora_do_intervalo"
    if not piso <= c.fechamento <= teto:
        return "fechamento_fora_do_intervalo"
    return None


def _tem_evento_proximo(datas_eventos: Sequence[date], inicio: date, fim: date) -> bool:
    return any(inicio - JANELA_EVENTO <= d <= fim + JANELA_EVENTO for d in datas_eventos)


def _salto(de: Candle, para: Candle) -> bool:
    return abs(para.fechamento / de.fechamento - 1) > VARIACAO_MAXIMA


def validar_candles(
    candles: Iterable[Candle],
    *,
    anterior: Candle | None = None,
    datas_eventos: Iterable[date] = (),
) -> tuple[list[Candle], list[Rejeicao], list[Rejeicao]]:
    """Separa candles válidos dos rejeitados e devolve alertas.

    `anterior` é o último candle já gravado, usado para checar a variação do
    primeiro candle novo. `datas_eventos` são as datas-com de eventos
    societários, que justificam variações acima de 50%.

    Uma variação acima de 50% sem evento conhecido é rejeitada quando é um pico
    isolado (o pregão seguinte volta ao nível anterior) ou quando ainda não há
    pregão seguinte para confirmá-la; como o job rebusca a partir do último
    pregão gravado, ela é reavaliada na próxima execução. Se o novo nível se
    mantém no pregão seguinte, o candle é aceito e vira um alerta
    (`salto_sem_evento`), porque o mais provável é um evento que a fonte não
    informou, e rejeitar travaria o ativo para sempre.
    """
    eventos = sorted(set(datas_eventos))
    validos: list[Candle] = []
    rejeitados: list[Rejeicao] = []
    alertas: list[Rejeicao] = []
    estruturais_ok: list[Candle] = []
    for c in sorted(candles, key=lambda x: x.data):
        motivo = _motivo_estrutural(c)
        if motivo:
            rejeitados.append(Rejeicao(c.data, motivo))
        else:
            estruturais_ok.append(c)

    referencia = anterior
    for i, c in enumerate(estruturais_ok):
        if referencia is not None and _salto(referencia, c):
            if _tem_evento_proximo(eventos, referencia.data, c.data):
                pass
            else:
                seguinte = estruturais_ok[i + 1] if i + 1 < len(estruturais_ok) else None
                if seguinte is None or _salto(c, seguinte):
                    rejeitados.append(Rejeicao(c.data, "variacao_acima_de_50pct"))
                    continue
                alertas.append(Rejeicao(c.data, "salto_sem_evento"))
        validos.append(c)
        referencia = c
    rejeitados.sort(key=lambda r: r.data)
    return validos, rejeitados, alertas
