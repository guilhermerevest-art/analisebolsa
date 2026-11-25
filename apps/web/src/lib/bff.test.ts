import { describe, expect, it } from "vitest";

import { cacheControl, caminhoApi, tagValida } from "./bff";

describe("BFF", () => {
  it("mapeia /api/* para /v1/*", () => {
    expect(caminhoApi(["ativos"])).toBe("/v1/ativos");
    expect(caminhoApi(["ativos", "PETR4", "cotacoes"])).toBe("/v1/ativos/PETR4/cotacoes");
    expect(caminhoApi(["mercado", "destaques"])).toBe("/v1/mercado/destaques");
  });

  it("bloqueia rotas fora da lista e segmentos suspeitos", () => {
    expect(caminhoApi([])).toBeNull();
    expect(caminhoApi(["health"])).toBeNull();
    expect(caminhoApi(["internal", "revalidate"])).toBeNull();
    expect(caminhoApi(["ativos", ".."])).toBeNull();
    expect(caminhoApi(["ativos", "PETR4%2F.."])).toBeNull();
  });

  it("admin nunca vai para cache público", () => {
    expect(cacheControl(["admin", "execucoes"])).toContain("no-store");
    expect(cacheControl(["watchlist", "PETR4"])).toContain("no-store");
    expect(cacheControl(["ativos"])).toContain("s-maxage");
  });

  it("valida tags de revalidação", () => {
    expect(tagValida("mercado")).toBe(true);
    expect(tagValida("ativo:PETR4")).toBe(true);
    expect(tagValida("ativo:petr4")).toBe(false);
    expect(tagValida("qualquer")).toBe(false);
  });
});
