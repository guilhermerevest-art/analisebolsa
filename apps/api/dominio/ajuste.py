"""Ajuste de preços por eventos societários.

O Yahoo já entrega o histórico ajustado. Este módulo serve às fontes que
devolvem preços brutos e decide quando o histórico precisa ser baixado de novo.
"""

from collections.abc import Iterable
from dataclasses import replace
from datetime import date
from decimal import Decimal

from dominio.modelos import Candle, Provento

CASAS = Decimal("0.0001")


def ajustar_por_eventos(candles: Iterable[Candle], eventos: Iterable[Provento]) -> list[Candle]:
    """Ajusta preços e volume anteriores a cada evento societário.

    Candles com data até a data-com do evento (inclusive) têm os preços
    divididos pelo fator e o volume multiplicado por ele. O
    `fechamento_ajustado` recebe o mesmo tratamento.
    """
    societarios = [e for e in eventos if e.societario and e.valor > 0]
    saida: list[Candle] = []
    for c in sorted(candles, key=lambda x: x.data):
        fator = Decimal(1)
        for e in societarios:
            if c.data <= e.data_com:
                fator *= e.valor
        if fator == 1:
            saida.append(c)
            continue
        saida.append(
            replace(
                c,
                abertura=(c.abertura / fator).quantize(CASAS),
                maxima=(c.maxima / fator).quantize(CASAS),
                minima=(c.minima / fator).quantize(CASAS),
                fechamento=(c.fechamento / fator).quantize(CASAS),
                fechamento_ajustado=(c.fechamento_ajustado / fator).quantize(CASAS),
                volume=int(c.volume * fator),
            )
        )
    return saida


def precisa_rebaixar_historico(
    novos: Iterable[Provento], primeira_data_historico: date | None
) -> bool:
    """Um provento novo para um ativo com histórico muda o `fechamento_ajustado`
    do passado, então o histórico completo precisa ser baixado de novo."""
    if primeira_data_historico is None:
        return False
    return any(p.data_com >= primeira_data_historico for p in novos)
