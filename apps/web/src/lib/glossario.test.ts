import { describe, expect, it } from "vitest";

import { CATEGORIAS, GLOSSARIO } from "@/lib/glossario";

describe("glossário", () => {
  const termos = Object.values(GLOSSARIO);

  it("todo termo tem categoria conhecida e explicação curta", () => {
    for (const t of termos) {
      expect(CATEGORIAS).toContain(t.categoria);
      expect(t.curto.length).toBeGreaterThan(20);
      expect(t.curto.length).toBeLessThan(260);
    }
  });

  it("explica sem linguagem de recomendação", () => {
    const textos = termos.map((t) => `${t.titulo} ${t.curto} ${"longo" in t ? t.longo : ""}`.toLowerCase()).join(" ");
    for (const proibida of ["recomend", "oportunidade", "melhor", "garantid", "barat", "chance", "probabilidade", "compre", "lucro certo"]) {
      expect(textos).not.toContain(proibida);
    }
  });
});
