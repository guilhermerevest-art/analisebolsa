import { describe, expect, it } from "vitest";

import { ESTRATEGIAS, leituraBacktest, lerParamsBacktest, PRONTAS, ultimoDiaDoMes } from "@/lib/backtest";

const HOJE = new Date("2026-11-26T12:00:00Z");

describe("lerParamsBacktest", () => {
  it("sem ativo não consulta e usa os padrões", () => {
    const { entrada, consulta } = lerParamsBacktest({}, HOJE);
    expect(consulta).toBeNull();
    expect(entrada.estrategia).toBe("cruzamento_mm");
    expect(entrada.inicio).toBe("2015-01");
  });

  it("só o ticker (atalho da página do ativo) já roda com os padrões", () => {
    const { consulta } = lerParamsBacktest({ ticker: "petr4" }, HOJE);
    expect(Object.fromEntries(consulta!)).toEqual({
      ticker: "PETR4",
      estrategia: "cruzamento_mm",
      inicio: "2015-01-01",
      curta: "20",
      longa: "100",
      capital: "10000",
      corretagem: "0",
      taxas: "0.03",
      deslizamento: "0.05",
      cdi_no_caixa: "true",
    });
  });

  it("manda só os parâmetros da estratégia escolhida, o stop e o fim", () => {
    const { consulta } = lerParamsBacktest(
      { ticker: "VALE3", estrategia: "rsi", rsi_periodo: "2", rsi_entrada: "10", curta: "999", stop: "2,5", fim: "2026-11", cdi: ["0"] },
      HOJE,
    );
    expect(consulta!.get("rsi_periodo")).toBe("2");
    expect(consulta!.get("curta")).toBeNull();
    expect(consulta!.get("stop_atr")).toBe("2.5");
    expect(consulta!.get("fim")).toBe("2026-11-26");
    expect(consulta!.get("cdi_no_caixa")).toBe("false");
  });

  it("aponta erros", () => {
    const { erros, consulta } = lerParamsBacktest(
      { ticker: "PETR4", estrategia: "cruzamento_mm", curta: "50", longa: "40", inicio: "2004-01", stop: "9", taxas: "x" },
      HOJE,
    );
    expect(consulta).toBeNull();
    expect(Object.keys(erros).sort()).toEqual(["curta", "inicio", "stop", "taxas"]);
    expect(lerParamsBacktest({ ticker: "PETR4", estrategia: "macd", macd_rapida: "30", macd_lenta: "20" }, HOJE).erros.macd_rapida).toBeTruthy();
    expect(lerParamsBacktest({ ticker: "PETR4", inicio: "2020-05", fim: "2020-05" }, HOJE).erros.fim).toBeTruthy();
  });

  it("estratégia desconhecida volta para a primeira", () => {
    expect(lerParamsBacktest({ ticker: "PETR4", estrategia: "xyz" }, HOJE).entrada.estrategia).toBe("cruzamento_mm");
  });
});

describe("estratégias prontas", () => {
  it("todas cabem nos limites da regra", () => {
    for (const p of PRONTAS) {
      const e = ESTRATEGIAS.find((x) => x.codigo === p.estrategia)!;
      expect(e).toBeTruthy();
      for (const [chave, valor] of Object.entries(p.parametros)) {
        const def = e.parametros.find((x) => x.chave === chave)!;
        expect(valor).toBeGreaterThanOrEqual(def.minimo);
        expect(valor).toBeLessThanOrEqual(def.maximo);
      }
    }
  });
});

it("ultimoDiaDoMes não passa de hoje", () => {
  expect(ultimoDiaDoMes("2024-02", HOJE)).toBe("2024-02-29");
  expect(ultimoDiaDoMes("2026-11", HOJE)).toBe("2026-11-26");
});

describe("leitura do backtest", () => {
  const base = { capital: 10000, estrategia: { retorno: 0.9713, queda: -0.42 }, manter: { retorno: 15.5134, queda: -0.6 }, cdi: { retorno: 2.0819 } };

  it("conta quanto o capital teria virado em cada caminho e compara", () => {
    const [valores, comparacao, queda, aviso] = leituraBacktest(base);
    expect(valores).toMatch(/R\$\s10\.000/);
    expect(valores).toContain("+97,1%");
    expect(valores).toMatch(/R\$\s19\.713/);
    expect(valores).toMatch(/R\$\s165\.134/);
    expect(comparacao).toBe("Nesse histórico, a regra rendeu menos que manter o ativo e menos que o CDI.");
    expect(queda).toContain("−42%");
    expect(aviso).toContain("passado");
  });

  it("descreve sem linguagem de recomendação", () => {
    const textos = [
      ...leituraBacktest(base),
      ...leituraBacktest({ ...base, estrategia: { retorno: 20, queda: -0.1 }, cdi: { retorno: null } }),
    ].join(" ").toLowerCase();
    for (const proibida of ["melhor", "compre", "recomend", "oportunidade", "garantid", "deve "]) expect(textos).not.toContain(proibida);
    expect(leituraBacktest({ ...base, estrategia: { retorno: 2.08, queda: null }, cdi: { retorno: 2.0819 } })[1]).toContain("praticamente o mesmo que o CDI");
  });
});
