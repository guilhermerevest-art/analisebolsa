"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";

import { chamarApi } from "@/lib/api";
import { esquemaOperacao, errosPorCampo, type ErrosCampos } from "@/lib/validacao";

export type EstadoOperacao = { erros?: ErrosCampos; ok?: number };

async function enviar(caminho: string, metodo: string, corpo?: unknown): Promise<{ ok: boolean; status: number; detalhe?: string; dados?: unknown }> {
  const resp = await chamarApi(caminho, {
    method: metodo,
    cache: "no-store",
    headers: corpo === undefined ? undefined : { "Content-Type": "application/json" },
    body: corpo === undefined ? undefined : JSON.stringify(corpo),
  });
  const dados = resp.status === 204 ? undefined : await resp.json().catch(() => undefined);
  const detalhe = (dados as { detail?: unknown } | undefined)?.detail;
  return { ok: resp.ok, status: resp.status, dados, detalhe: typeof detalhe === "string" ? detalhe : undefined };
}

const id = (v: FormDataEntryValue | null) => {
  const n = Number(v);
  return Number.isInteger(n) && n > 0 ? n : null;
};

export async function criarCarteira(form: FormData): Promise<void> {
  const nome = String(form.get("nome") ?? "").trim() || "Minha carteira";
  const r = await enviar("/v1/carteiras", "POST", { nome: nome.slice(0, 60) });
  revalidatePath("/carteira");
  const nova = r.ok ? (r.dados as { id: number }).id : null;
  redirect(nova ? `/carteira?c=${nova}` : "/carteira");
}

export async function renomearCarteira(form: FormData): Promise<void> {
  const c = id(form.get("carteira"));
  const nome = String(form.get("nome") ?? "").trim().slice(0, 60);
  if (c && nome) await enviar(`/v1/carteiras/${c}`, "PATCH", { nome });
  revalidatePath("/carteira");
}

export async function excluirCarteira(form: FormData): Promise<void> {
  const c = id(form.get("carteira"));
  if (c) await enviar(`/v1/carteiras/${c}`, "DELETE");
  revalidatePath("/carteira");
  redirect("/carteira");
}

export async function lancarOperacao(_: EstadoOperacao, form: FormData): Promise<EstadoOperacao> {
  const c = id(form.get("carteira"));
  if (!c) return { erros: { form: "Carteira inválida" } };
  const parsed = esquemaOperacao.safeParse(Object.fromEntries(["ticker", "tipo", "data", "quantidade", "preco", "custos"].map((k) => [k, String(form.get(k) ?? "")])));
  if (!parsed.success) return { erros: errosPorCampo(parsed.error) };
  const r = await enviar(`/v1/carteiras/${c}/operacoes`, "POST", parsed.data);
  if (!r.ok) return { erros: { form: r.detalhe ?? "Não foi possível lançar a operação" } };
  revalidatePath("/carteira");
  return { ok: Date.now() };
}

export async function removerOperacao(form: FormData): Promise<void> {
  const c = id(form.get("carteira"));
  const op = id(form.get("operacao"));
  if (c && op) await enviar(`/v1/carteiras/${c}/operacoes/${op}`, "DELETE");
  revalidatePath("/carteira");
}
