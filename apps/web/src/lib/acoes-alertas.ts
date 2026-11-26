"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";

import { enviarApi } from "@/lib/api";
import { esquemaAlerta, errosPorCampo, type ErrosCampos } from "@/lib/validacao";

export type EstadoAlerta = { erros?: ErrosCampos; ok?: number };

const id = (v: FormDataEntryValue | null) => {
  const n = Number(v);
  return Number.isInteger(n) && n > 0 ? n : null;
};

export async function criarAlerta(_: EstadoAlerta, form: FormData): Promise<EstadoAlerta> {
  const parsed = esquemaAlerta.safeParse(Object.fromEntries(["ticker", "tipo", "parametro", "codigo"].map((k) => [k, String(form.get(k) ?? "")])));
  if (!parsed.success) return { erros: errosPorCampo(parsed.error) };
  const r = await enviarApi("/v1/alertas", "POST", parsed.data);
  if (r.status === 404) return { erros: { ticker: "Ativo não encontrado" } };
  if (!r.ok) return { erros: { form: r.detalhe ?? "Não foi possível criar o alerta" } };
  revalidatePath("/alertas");
  return { ok: Date.now() };
}

export async function alternarAlerta(form: FormData): Promise<void> {
  const a = id(form.get("alerta"));
  if (a) await enviarApi(`/v1/alertas/${a}`, "PATCH", { ativo: form.get("ativo") === "1" });
  revalidatePath("/alertas");
}

export async function excluirAlerta(form: FormData): Promise<void> {
  const a = id(form.get("alerta"));
  if (a) await enviarApi(`/v1/alertas/${a}`, "DELETE");
  revalidatePath("/alertas");
}

export async function salvarAvisosCarteira(form: FormData): Promise<void> {
  const tipos = ["proventos", "data_com", "darf", "vencimentos"] as const;
  await enviarApi("/v1/alertas/carteira", "PUT", Object.fromEntries(tipos.map((t) => [t, form.get(t) === "on"])));
  revalidatePath("/alertas");
  redirect("/alertas?avisos=1#avisos-carteira");
}
