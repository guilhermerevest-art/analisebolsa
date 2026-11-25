import { describe, expect, it } from "vitest";

import { roleParaEmail, emailsAdmin } from "./env";
import { destinoSeguro, errosPorCampo, esquemaAlerta, esquemaCadastro, esquemaEntrar, esquemaOperacao } from "./validacao";

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

describe("esquemaOperacao", () => {
  const base = { ticker: "petr4", tipo: "compra", data: "2024-03-01", quantidade: "100", preco: "38,63", custos: "" };
  it("normaliza números no formato brasileiro", () => {
    const r = esquemaOperacao.parse({ ...base, quantidade: "1.000", preco: "R$ 1.234,56", custos: "4,90" });
    expect(r).toEqual({ ticker: "PETR4", tipo: "compra", data: "2024-03-01", quantidade: "1000", preco: "1234.56", custos: "4.90" });
    expect(esquemaOperacao.parse(base).custos).toBe("0");
  });
  it("rejeita valores inválidos", () => {
    const erros = (campos: object) => errosPorCampo(esquemaOperacao.safeParse({ ...base, ...campos }).error!);
    expect(erros({ quantidade: "0" }).quantidade).toMatch(/maior que zero/);
    expect(erros({ preco: "abc" }).preco).toMatch(/inválido/);
    expect(erros({ preco: "1,23456" }).preco).toMatch(/4 casas/);
    expect(erros({ data: "01/03/2024" }).data).toBe("Data inválida");
    expect(erros({ ticker: "PETR-4" }).ticker).toBe("Ticker inválido");
    expect(erros({ tipo: "aluguel" }).tipo).toBeDefined();
  });
});

describe("esquemaAlerta", () => {
  it("preço em formato brasileiro", () => {
    expect(esquemaAlerta.parse({ ticker: " petr4", tipo: "preco_acima", parametro: "1.040,50", codigo: "" })).toEqual({
      ticker: "PETR4",
      tipo: "preco_acima",
      parametro: 1040.5,
    });
  });
  it("sinal exige código e ignora o parâmetro", () => {
    expect(esquemaAlerta.parse({ ticker: "VALE3", tipo: "insight", parametro: "x", codigo: "maxima_52s" })).toEqual({
      ticker: "VALE3",
      tipo: "insight",
      codigo: "maxima_52s",
    });
    expect(esquemaAlerta.safeParse({ ticker: "VALE3", tipo: "insight", parametro: "", codigo: "" }).success).toBe(false);
  });
  it("valida valor e variação", () => {
    expect(esquemaAlerta.safeParse({ ticker: "VALE3", tipo: "preco_abaixo", parametro: "0", codigo: "" }).success).toBe(false);
    expect(esquemaAlerta.safeParse({ ticker: "VALE3", tipo: "variacao_dia", parametro: "150", codigo: "" }).success).toBe(false);
    expect(esquemaAlerta.safeParse({ ticker: "X", tipo: "variacao_dia", parametro: "5", codigo: "" }).success).toBe(false);
  });
});
