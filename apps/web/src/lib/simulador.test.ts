import { describe, expect, it } from "vitest";

import { fimDeCadaAno, lerParamsSimulador, mesMaximo } from "./simulador";

const hoje = new Date("2026-11-25T12:00:00Z");

describe("lerParamsSimulador", () => {
  it("sem envio, não consulta", () => {
    expect(lerParamsSimulador({}, hoje).consulta).toBeNull();
  });

  it("monta a consulta da API", () => {
    const { consulta, erros } = lerParamsSimulador({ ticker: " petr4", inicio: "2015-01", inicial: "1.000", mensal: "500,50" }, hoje);
    expect(erros).toEqual({});
    expect(Object.fromEntries(consulta!)).toEqual({
      inicio: "2015-01-01",
      aporte_inicial: "1000",
      aporte_mensal: "500.50",
      reinvestir: "true",
      ticker: "PETR4",
    });
  });

  it("checkbox desmarcado manda só o 0; marcado manda 0 e 1", () => {
    expect(lerParamsSimulador({ inicio: "2015-01", mensal: "1", reinvestir: "0" }, hoje).consulta!.get("reinvestir")).toBe("false");
    expect(lerParamsSimulador({ inicio: "2015-01", mensal: "1", reinvestir: ["0", "1"] }, hoje).consulta!.get("reinvestir")).toBe("true");
  });

  it("valida campos", () => {
    const { erros, consulta } = lerParamsSimulador({ ticker: "X!", inicio: "2004-12", inicial: "abc", mensal: "1e9" }, hoje);
    expect(consulta).toBeNull();
    expect(Object.keys(erros).sort()).toEqual(["inicial", "inicio", "mensal", "ticker"]);
    expect(lerParamsSimulador({ inicio: "2026-11", mensal: "1" }, hoje).erros.inicio).toContain("10/2026");
    expect(lerParamsSimulador({ inicio: "2020-01" }, hoje).erros.aportes).toBeDefined();
  });

  it("mês máximo atravessa o ano", () => {
    expect(mesMaximo(new Date("2027-01-10T12:00:00Z"))).toBe("2026-12");
  });
});

it("fimDeCadaAno pega o último ponto de cada ano", () => {
  const pontos = ["2024-11-29", "2024-12-31", "2025-01-31", "2025-02-28"].map((data) => ({ data }));
  expect(fimDeCadaAno(pontos).map((p) => p.data)).toEqual(["2024-12-31", "2025-02-28"]);
});
