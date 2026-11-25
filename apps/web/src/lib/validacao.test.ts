import { describe, expect, it } from "vitest";

import { roleParaEmail, emailsAdmin } from "./env";
import { destinoSeguro, errosPorCampo, esquemaCadastro, esquemaEntrar } from "./validacao";

describe("validação dos formulários", () => {
  it("normaliza o e-mail", () => {
    const r = esquemaEntrar.parse({ email: "  Fulano@Exemplo.COM ", senha: "x" });
    expect(r.email).toBe("fulano@exemplo.com");
  });

  it("exige senha de 8 caracteres e confirmação igual", () => {
    const r = esquemaCadastro.safeParse({ nome: "Ana", email: "ana@ex.com", senha: "1234567", confirmacao: "x" });
    expect(r.success).toBe(false);
    if (!r.success) {
      const erros = errosPorCampo(r.error);
      expect(erros.senha).toContain("8 caracteres");
    }
    const r2 = esquemaCadastro.safeParse({ nome: "Ana", email: "ana@ex.com", senha: "12345678", confirmacao: "12345679" });
    expect(r2.success).toBe(false);
    if (!r2.success) expect(errosPorCampo(r2.error).confirmacao).toBe("As senhas não conferem");
  });

  it("aceita cadastro válido", () => {
    expect(
      esquemaCadastro.safeParse({ nome: "Ana", email: "ana@ex.com", senha: "12345678", confirmacao: "12345678" }).success,
    ).toBe(true);
  });
});

describe("ADMIN_EMAILS", () => {
  it("compara sem diferenciar maiúsculas e ignora espaços", () => {
    const admins = emailsAdmin(" Admin@Ex.com , outro@ex.com,");
    expect(roleParaEmail("admin@ex.com", admins)).toBe("admin");
    expect(roleParaEmail("ADMIN@EX.COM", admins)).toBe("admin");
    expect(roleParaEmail("user@ex.com", admins)).toBe("user");
    expect(roleParaEmail(null, admins)).toBe("user");
  });
});

describe("destinoSeguro", () => {
  it("aceita caminhos internos", () => {
    expect(destinoSeguro("/ativo/PETR4")).toBe("/ativo/PETR4");
    expect(destinoSeguro("/watchlist")).toBe("/watchlist");
  });
  it("rejeita URLs externas e valores estranhos", () => {
    for (const v of ["//evil.com", "https://evil.com", "/\\evil.com", "javascript:alert(1)", "", null, 3, "/a b"]) {
      expect(destinoSeguro(v)).toBe("/conta");
    }
  });
});
