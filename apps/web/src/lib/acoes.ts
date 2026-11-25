"use server";

import { hash } from "@node-rs/argon2";
import { eq } from "drizzle-orm";
import { AuthError } from "next-auth";

import { signIn, signOut } from "@/auth";
import { db, schema } from "@/lib/db";
import { roleParaEmail } from "@/lib/env";
import { type ErrosCampos, errosPorCampo, esquemaCadastro, esquemaEntrar } from "@/lib/validacao";

export type EstadoForm = { erros?: ErrosCampos; valores?: Record<string, string> };

function valores(form: FormData, campos: string[]): Record<string, string> {
  return Object.fromEntries(campos.map((c) => [c, String(form.get(c) ?? "")]));
}

export async function entrar(_: EstadoForm, form: FormData): Promise<EstadoForm> {
  const dados = valores(form, ["email", "senha"]);
  const parsed = esquemaEntrar.safeParse(dados);
  if (!parsed.success) return { erros: errosPorCampo(parsed.error), valores: { email: dados.email } };
  try {
    await signIn("credentials", { ...parsed.data, redirectTo: "/conta" });
  } catch (e) {
    if (e instanceof AuthError) {
      return { erros: { form: "E-mail ou senha incorretos" }, valores: { email: dados.email } };
    }
    throw e; // o redirect do Next.js é lançado como exceção
  }
  return {};
}

export async function cadastrar(_: EstadoForm, form: FormData): Promise<EstadoForm> {
  const dados = valores(form, ["nome", "email", "senha", "confirmacao"]);
  const manter = { nome: dados.nome, email: dados.email };
  const parsed = esquemaCadastro.safeParse(dados);
  if (!parsed.success) return { erros: errosPorCampo(parsed.error), valores: manter };

  const { nome, email, senha } = parsed.data;
  const [existente] = await db()
    .select({ id: schema.users.id })
    .from(schema.users)
    .where(eq(schema.users.email, email))
    .limit(1);
  if (existente) return { erros: { email: "Já existe uma conta com este e-mail" }, valores: manter };

  // @node-rs/argon2 usa Argon2id por padrão
  const passwordHash = await hash(senha, { memoryCost: 19456, timeCost: 2, parallelism: 1 });
  await db().insert(schema.users).values({ name: nome, email, passwordHash, role: roleParaEmail(email) });
  await signIn("credentials", { email, senha, redirectTo: "/conta" });
  return {};
}

export async function entrarComGoogle() {
  await signIn("google", { redirectTo: "/conta" });
}

export async function sair() {
  await signOut({ redirectTo: "/" });
}
