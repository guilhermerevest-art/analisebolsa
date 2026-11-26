"""Cotas dos fundos que estão em alguma carteira: `python -m worker.fundos`.

Baixa um arquivo mensal da CVM por mês necessário: sempre o mês atual e o anterior (a CVM
republica dias recentes) e, para trás, só os meses em que algum fundo ainda não tem cota.
"""

import logging
import sys
from datetime import date

from sqlalchemy import Engine, text

from fontes.cvm import INICIO, CvmFonte

log = logging.getLogger("worker.fundos")


def _meses(inicio: date, fim: date) -> list[tuple[int, int]]:
    a, m = inicio.year, inicio.month
    saida = []
    while (a, m) <= (fim.year, fim.month):
        saida.append((a, m))
        a, m = (a + 1, 1) if m == 12 else (a, m + 1)
    return saida


def atualizar_fundos(engine: Engine, hoje: date, fonte: CvmFonte | None = None) -> dict:
    with engine.connect() as conn:
        pedidos = conn.execute(
            text(
                "SELECT cnpj, min(data_aplicacao) FROM investimentos "
                "WHERE cnpj IS NOT NULL GROUP BY cnpj"
            )
        ).all()
        if not pedidos:
            return {"fundos": 0}
        tem = {
            (cnpj, (int(a), int(m)))
            for cnpj, a, m in conn.execute(
                text(
                    "SELECT DISTINCT cnpj, extract(year FROM data), extract(month FROM data) "
                    "FROM cotas_fundos WHERE cnpj = ANY(:c)"
                ),
                {"c": [p[0] for p in pedidos]},
            )
        }
    fonte = fonte or CvmFonte()
    recentes = set(_meses(date(hoje.year - (hoje.month == 1), (hoje.month - 2) % 12 + 1, 1), hoje))
    gravadas = meses = 0
    erros: list[str] = []
    for mes in _meses(max(INICIO, min(p[1] for p in pedidos)), hoje):
        faltam = {
            cnpj
            for cnpj, desde in pedidos
            if (desde.year, desde.month) <= mes and (cnpj, mes) not in tem
        }
        if mes in recentes:
            faltam = {cnpj for cnpj, desde in pedidos if (desde.year, desde.month) <= mes}
        if not faltam:
            continue
        try:
            linhas = fonte.mes(*mes, faltam)
        except Exception as e:  # um mês com problema não impede os outros
            erros.append(f"{mes[0]}-{mes[1]:02d}: {e}"[:120])
            continue
        meses += 1
        if linhas:
            with engine.begin() as conn:
                conn.execute(
                    text(
                        "INSERT INTO cotas_fundos (cnpj, data, cota) VALUES (:c, :d, :v) "
                        "ON CONFLICT (cnpj, data) DO UPDATE SET cota = EXCLUDED.cota"
                    ),
                    [{"c": c, "d": d, "v": v} for c, d, v in linhas],
                )
            gravadas += len(linhas)
    return {
        "fundos": len(pedidos),
        "meses": meses,
        "cotas": gravadas,
        **({"erros": erros} if erros else {}),
    }


def main() -> int:
    from app.db import get_engine
    from worker.eod import hoje_b3

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    res = atualizar_fundos(get_engine(), hoje_b3())
    log.info("fundos: %s", res)
    return 0


if __name__ == "__main__":
    sys.exit(main())
