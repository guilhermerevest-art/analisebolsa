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
