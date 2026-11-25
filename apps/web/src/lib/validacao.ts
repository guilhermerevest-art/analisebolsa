import { z } from "zod";

import { SENHA_MINIMA } from "./constantes";

export { SENHA_MINIMA };

export const esquemaEntrar = z.object({
  email: z.string().trim().toLowerCase().pipe(z.email("E-mail inválido")),
  senha: z.string().min(1, "Informe a senha"),
});

export const esquemaCadastro = z
  .object({
    nome: z.string().trim().min(2, "Informe seu nome").max(80),
    email: z.string().trim().toLowerCase().pipe(z.email("E-mail inválido")),
    senha: z
      .string()
      .min(SENHA_MINIMA, `A senha precisa ter pelo menos ${SENHA_MINIMA} caracteres`)
      .max(128),
    confirmacao: z.string(),
  })
  .refine((d) => d.senha === d.confirmacao, {
    message: "As senhas não conferem",
    path: ["confirmacao"],
  });

export type ErrosCampos = Partial<Record<string, string>>;

export function errosPorCampo(erro: z.ZodError): ErrosCampos {
  const saida: ErrosCampos = {};
  for (const issue of erro.issues) {
    const campo = String(issue.path[0] ?? "form");
    saida[campo] ??= issue.message;
  }
  return saida;
}

/** Caminho interno para voltar depois do login; qualquer outra coisa vira /conta. */
export function destinoSeguro(valor: unknown): string {
  if (typeof valor !== "string" || valor.length > 200) return "/conta";
  return /^\/(?![/\\])[A-Za-z0-9/_\-?=&%.]*$/.test(valor) ? valor : "/conta";
}

/** "1.234,56", "1.000" ou "1234.56" -> número com ponto decimal; null se não for número. */
export function decimalBr(valor: string): string | null {
  let v = valor.trim().replace(/\s|R\$/g, "");
  // Com vírgula, os pontos são de milhar; sem vírgula, "1.000" também é milhar e "38.63" é decimal.
  if (v.includes(",") || /^\d{1,3}(\.\d{3})+$/.test(v)) v = v.replace(/\./g, "").replace(",", ".");
  return /^\d+(\.\d+)?$/.test(v) ? v : null;
}

function campoDecimal(rotulo: string, casas: number, minimo: "positivo" | "zero") {
  return z
    .string()
    .transform((v, ctx) => {
      if (minimo === "zero" && v.trim() === "") return "0";
      const d = decimalBr(v);
      if (d === null) {
        ctx.addIssue({ code: "custom", message: `${rotulo} inválido` });
        return z.NEVER;
      }
      if ((d.split(".")[1] ?? "").length > casas) {
        ctx.addIssue({ code: "custom", message: `${rotulo}: no máximo ${casas} casas decimais` });
        return z.NEVER;
      }
      if (minimo === "positivo" && Number(d) <= 0) {
        ctx.addIssue({ code: "custom", message: `${rotulo} precisa ser maior que zero` });
        return z.NEVER;
      }
      return d;
    });
}

export const esquemaOperacao = z.object({
  ticker: z
    .string()
    .trim()
    .toUpperCase()
    .regex(/^[A-Z0-9]{4,6}$/, "Ticker inválido"),
  tipo: z.enum(["compra", "venda"], "Escolha compra ou venda"),
  data: z.iso.date("Data inválida"),
  quantidade: campoDecimal("Quantidade", 4, "positivo"),
  preco: campoDecimal("Preço", 4, "positivo"),
  custos: campoDecimal("Custos", 2, "zero"),
});
