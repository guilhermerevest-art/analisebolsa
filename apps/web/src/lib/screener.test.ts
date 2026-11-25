import { describe, expect, it } from "vitest";

import { LIQUIDEZ_PADRAO, ordemValida, paramsParaApi, PRESETS, proximaOrdem, urlCom, urlPreset } from "./screener";

describe("paramsParaApi", () => {
  it("aplica liquidez padrão, ordem e paginação", () => {
    const p = paramsParaApi({});
    expect(p.get("volume_financeiro_20d_min")).toBe(String(LIQUIDEZ_PADRAO));
    expect(p.get("ordem")).toBe("-volume_financeiro_20d");
    expect(p.get("pagina")).toBe("1");
  });

  it("liquidez=todas remove o filtro padrão", () => {
    expect(paramsParaApi({ liquidez: "todas" }).has("volume_financeiro_20d_min")).toBe(false);
  });

  it("repassa só parâmetros conhecidos e números válidos", () => {
    const p = paramsParaApi({ dy_12m_min: "6,5", pl_max: "abc", foo: "1", rsi14_max: "", tipo: ["fii", "xpto"], tendencia: "subindo" });
    expect(p.get("dy_12m_min")).toBe("6.5");
    expect(p.has("pl_max")).toBe(false);
    expect(p.has("foo")).toBe(false);
    expect(p.has("rsi14_max")).toBe(false);
    expect(p.getAll("tipo")).toEqual(["fii"]);
    expect(p.has("tendencia")).toBe(false);
  });

  it("página inválida volta para 1", () => {
    expect(paramsParaApi({ pagina: "-3" }).get("pagina")).toBe("1");
    expect(paramsParaApi({ pagina: "4" }).get("pagina")).toBe("4");
  });
});

describe("ordem", () => {
  it("rejeita coluna desconhecida", () => {
    expect(ordemValida("-nome")).toBe("-volume_financeiro_20d");
    expect(ordemValida("pl")).toBe("pl");
  });

  it("inverte a mesma coluna e começa decrescente em coluna nova", () => {
    expect(proximaOrdem("-pl", "pl")).toBe("pl");
    expect(proximaOrdem("pl", "pl")).toBe("-pl");
    expect(proximaOrdem("-pl", "dy_12m")).toBe("-dy_12m");
    expect(proximaOrdem("-pl", "ticker")).toBe("ticker");
  });
});

describe("urlCom", () => {
  it("altera, remove e volta à página 1 ao mudar filtro", () => {
    expect(urlCom({ pl_max: "10", pagina: "3" }, { dy_12m_min: "5" })).toBe("/screener?pl_max=10&dy_12m_min=5");
    expect(urlCom({ pl_max: "10" }, { pl_max: null })).toBe("/screener");
    expect(urlCom({ pl_max: "10" }, { pagina: "2" })).toBe("/screener?pl_max=10&pagina=2");
  });
});

describe("presets", () => {
  it("têm ids únicos e só usam parâmetros que a API aceita", () => {
    expect(new Set(PRESETS.map((p) => p.id)).size).toBe(PRESETS.length);
    for (const preset of PRESETS) {
      const api = paramsParaApi(preset.params);
      for (const k of Object.keys(preset.params)) expect(api.has(k)).toBe(true);
      expect(urlPreset(preset)).toMatch(/^\/screener\?/);
    }
  });

  it("não usam linguagem de recomendação", () => {
    const textos = PRESETS.map((p) => `${p.titulo} ${p.descricao}`.toLowerCase()).join(" ");
    for (const proibida of ["melhor", "compre", "venda", "oportunidade", "recomend"]) expect(textos).not.toContain(proibida);
  });
});
