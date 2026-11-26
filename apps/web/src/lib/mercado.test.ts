import { describe, expect, it } from "vitest";

import { caminhoMiniatura, formatarIndicador, inicioDoPeriodo } from "@/lib/mercado";

describe("mercado", () => {
  it("formata cada unidade", () => {
    expect(formatarIndicador(173353.27, "pontos")).toBe("173.353");
    expect(formatarIndicador(3541.11, "pontos")).toBe("3.541,11");
    expect(formatarIndicador(5.7446, "reais")).toMatch(/R\$\s5,7446/);
    expect(formatarIndicador(60590.57, "dolares")).toMatch(/US\$\s60\.591/);
  });

  it("calcula o início do período sem passar de 2005", () => {
    const hoje = new Date("2026-11-26T12:00:00Z");
    expect(inicioDoPeriodo("1a", hoje)).toBe("2025-11-26");
    expect(inicioDoPeriodo("max", hoje)).toBe("2005-01-01");
  });

  it("desenha a minissérie do mínimo (embaixo) ao máximo (em cima)", () => {
    expect(caminhoMiniatura([1, 3, 2], 100, 10)).toBe("M0.0,10.0L50.0,0.0L100.0,5.0");
    expect(caminhoMiniatura([1])).toBe("");
  });
});
