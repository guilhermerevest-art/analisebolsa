import { describe, expect, it } from "vitest";

import { roleParaEmail, emailsAdmin } from "./env";
import { errosPorCampo, esquemaCadastro, esquemaEntrar } from "./validacao";

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
