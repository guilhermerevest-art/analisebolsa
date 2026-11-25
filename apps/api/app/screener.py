"""Screener (Fase 2, seção 4 da spec): filtros em lista fechada sobre `metricas_ativo`.

Nenhum nome de coluna vem do cliente: os campos aceitos estão em `CAMPOS`, e os
valores entram como parâmetros do SQL.
"""

from dataclasses import dataclass
from typing import Literal

from sqlalchemy import Connection, text

Unidade = Literal["pct", "brl", "numero"]


@dataclass(frozen=True)
class Campo:
    campo: str
    rotulo: str
    unidade: Unidade
    grupo: Literal["preco", "tecnico", "fundamentos"]
    descricao: str


CAMPOS: tuple[Campo, ...] = (
    Campo("preco", "Preço", "brl", "preco", "Último fechamento"),
    Campo("var_1m", "Variação 1 mês", "pct", "preco", "Retorno total em 30 dias"),
    Campo("var_12m", "Variação 12 meses", "pct", "preco", "Retorno total em 12 meses"),
    Campo("volatilidade_12m", "Volatilidade", "pct", "tecnico",
          "Desvio-padrão anualizado dos retornos diários em 12 meses"),
    Campo("pos_52s", "Posição em 52 semanas", "pct", "tecnico",
          "0% na mínima e 100% na máxima das últimas 52 semanas"),
    Campo("dist_mm200", "Distância da MM200", "pct", "tecnico",
          "Quanto o preço está acima (+) ou abaixo (−) da média de 200 pregões"),
    Campo("rsi14", "RSI (14)", "numero", "tecnico",
          "Índice de força relativa: acima de 70 se chama sobrecompra; abaixo de 30, sobrevenda"),
    Campo("volume_financeiro_20d", "Liquidez diária", "brl", "tecnico",
          "Média do volume financeiro negociado nos últimos 20 pregões"),
    Campo("pl", "P/L", "numero", "fundamentos", "Preço sobre lucro por ação"),
    Campo("pvp", "P/VP", "numero", "fundamentos", "Preço sobre valor patrimonial por ação"),
    Campo("dy_12m", "Dividend yield", "pct", "fundamentos",
          "Proventos pagos em 12 meses sobre o preço"),
    Campo("roe", "ROE", "pct", "fundamentos", "Lucro líquido sobre patrimônio líquido"),
    Campo("margem_liquida", "Margem líquida", "pct", "fundamentos", "Lucro líquido sobre receita"),
    Campo("div_liq_ebitda", "Dív. líq./EBITDA", "numero", "fundamentos",
          "Dívida líquida sobre EBITDA"),
    Campo("valor_mercado", "Valor de mercado", "brl", "fundamentos", "Preço × total de ações"),
)  # fmt: skip
NOMES = tuple(c.campo for c in CAMPOS)
ORDENAVEIS = (*NOMES, "ticker", "var_1d", "var_ano")

COLUNAS_SAIDA = """
  a.ticker, a.nome, a.tipo, a.setor, a.logo_url,
  m.data, m.preco, m.var_1d, m.var_1m, m.var_3m, m.var_6m, m.var_12m, m.var_ano,
  m.volatilidade_12m, m.drawdown_12m, m.max_52s, m.min_52s, m.pos_52s, m.dist_mm50,
  m.dist_mm200, m.rsi14, m.tendencia, m.volume_financeiro_20d::float AS volume_financeiro_20d,
  m.pl, m.pvp, m.dy_12m, m.roe, m.margem_liquida, m.div_liq_ebitda,
  m.valor_mercado::float AS valor_mercado
"""


def buscar(
    conn: Connection,
    faixas: dict[str, tuple[float | None, float | None]],
    tipos: list[str] | None,
    setor: str | None,
    tendencia: str | None,
    ordem: str,
    pagina: int,
    limite: int,
) -> tuple[list[dict], int]:
    condicoes = ["a.ativo"]
    params: dict = {}
    for campo, (minimo, maximo) in faixas.items():
        assert campo in NOMES  # garantido pelo schema; defesa extra contra SQL dinâmico
        if minimo is not None:
            condicoes.append(f"m.{campo} >= :{campo}_min")
            params[f"{campo}_min"] = minimo
        if maximo is not None:
            condicoes.append(f"m.{campo} <= :{campo}_max")
            params[f"{campo}_max"] = maximo
    if tipos:
        condicoes.append("a.tipo = ANY(:tipos)")
        params["tipos"] = tipos
    if setor:
        condicoes.append("a.setor = :setor")
        params["setor"] = setor
    if tendencia:
        condicoes.append("m.tendencia = :tendencia")
        params["tendencia"] = tendencia

    desc = ordem.startswith("-")
    coluna = ordem.lstrip("-")
    assert coluna in ORDENAVEIS
    expr = "a.ticker" if coluna == "ticker" else f"m.{coluna}"
    params |= {"limite": limite, "offset": (pagina - 1) * limite}
    linhas = conn.execute(
        text(
            f"""
            SELECT {COLUNAS_SAIDA}, count(*) OVER () AS total
            FROM metricas_ativo m JOIN ativos a USING (ativo_id)
            WHERE {" AND ".join(condicoes)}
            ORDER BY {expr} {"DESC" if desc else "ASC"} NULLS LAST, a.ticker
            LIMIT :limite OFFSET :offset
            """
        ),
        params,
    ).mappings()
    itens = [dict(r) for r in linhas]
    total = itens[0].pop("total") if itens else 0
    for i in itens[1:]:
        i.pop("total")
    if not itens and pagina > 1:
        total = contar(conn, condicoes, params)
    return itens, total


def contar(conn: Connection, condicoes: list[str], params: dict) -> int:
    return conn.execute(
        text(
            "SELECT count(*) FROM metricas_ativo m JOIN ativos a USING (ativo_id) "
            f"WHERE {' AND '.join(condicoes)}"
        ),
        params,
    ).scalar_one()


def faixas_observadas(conn: Connection) -> dict[str, tuple[float | None, float | None]]:
    """Percentis 1% e 99% de cada campo, para a UI sugerir limites sem outliers."""
    partes = ", ".join(
        f"percentile_cont(0.01) WITHIN GROUP (ORDER BY m.{c}) AS {c}_min, "
        f"percentile_cont(0.99) WITHIN GROUP (ORDER BY m.{c}) AS {c}_max"
        for c in NOMES
    )
    sql = f"SELECT {partes} FROM metricas_ativo m JOIN ativos a USING (ativo_id) WHERE a.ativo"
    r = conn.execute(text(sql)).mappings().one()
    return {c: (r[f"{c}_min"], r[f"{c}_max"]) for c in NOMES}


def setores(conn: Connection) -> list[str]:
    return list(
        conn.execute(
            text(
                "SELECT DISTINCT a.setor FROM ativos a JOIN metricas_ativo m USING (ativo_id) "
                "WHERE a.ativo AND a.setor IS NOT NULL ORDER BY a.setor"
            )
        ).scalars()
    )
