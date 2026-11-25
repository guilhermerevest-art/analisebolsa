import { describe, expect, it } from "vitest";

import { classeVariacao, formatarCompacto, formatarData, formatarPct, formatarPreco } from "./formato";

const nbsp = (s: string) => s.replace(/ /g, " ");

describe("formatação", () => {
  it("preço em reais, com mais casas abaixo de R$ 1", () => {
    expect(nbsp(formatarPreco("38.63"))).toBe("R$ 38,63");
    expect(nbsp(formatarPreco("1234.5"))).toBe("R$ 1.234,50");
    expect(nbsp(formatarPreco("0.1234"))).toBe("R$ 0,1234");
    expect(formatarPreco(null)).toBe("—");
    expect(formatarPreco("abc")).toBe("—");
  });

  it("variação com sinal", () => {
    expect(formatarPct(1.234)).toBe("+1,23%");
    expect(formatarPct(-0.45)).toBe("−0,45%");
    expect(formatarPct(0)).toBe("0%");
    expect(formatarPct(null)).toBe("—");
  });

  it("data ISO sem fuso", () => {
    expect(formatarData("2025-06-04")).toBe("04/06/2025");
    expect(formatarData(null)).toBe("—");
  });

  it("compacto e classes", () => {
    expect(nbsp(formatarCompacto(569288804804))).toMatch(/569,3 bi/);
    expect(classeVariacao(1)).toBe("text-positivo");
    expect(classeVariacao(-1)).toBe("text-destructive");
    expect(classeVariacao(0)).toBe("text-muted-foreground");
  });
});
