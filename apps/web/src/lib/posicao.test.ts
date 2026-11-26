import { describe, expect, it } from "vitest";

import { lerParamsPosicao } from "@/lib/posicao";

describe("lerParamsPosicao", () => {
  it("sem capital só preenche o formulário", () => {
    const { entrada, consulta } = lerParamsPosicao({ ticker: "petr4" });
    expect(consulta).toBeNull();
    expect(entrada.ticker).toBe("PETR4");
  });

  it("monta a consulta com stop manual", () => {
    const { consulta } = lerParamsPosicao({ capital: "100.000", entrada: "30,50", stop: "28", risco: "1,5" });
    expect(Object.fromEntries(consulta!)).toEqual({ lote: "100", capital: "100000", risco: "1.5", concentracao: "25", entrada: "30.50", stop: "28" });
  });

  it("stop por ATR usa o ativo e dispensa a entrada", () => {
    const { consulta } = lerParamsPosicao({ capital: "50000", ticker: "VALE3", modo: "atr", atr: "2", lote: "1" });
    expect(consulta!.get("atr_mult")).toBe("2");
    expect(consulta!.get("entrada")).toBeNull();
    expect(consulta!.get("lote")).toBe("1");
  });

  it("aponta erros", () => {
    expect(lerParamsPosicao({ capital: "1000", entrada: "30", stop: "31" }).erros.stop).toMatch(/abaixo/);
    expect(lerParamsPosicao({ capital: "1000", modo: "atr", entrada: "30" }).erros.atr).toBeTruthy();
    expect(Object.keys(lerParamsPosicao({ capital: "x", risco: "9" }).erros).sort()).toEqual(["capital", "entrada", "risco", "stop"]);
  });
});
