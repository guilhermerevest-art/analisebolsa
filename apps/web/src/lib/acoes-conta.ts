"use server";

import { signOut } from "@/auth";
import { enviarApi } from "@/lib/api";

export type EstadoExclusao = { erro?: string };

/** Exclui a conta na API (tudo sai em cascata) e encerra a sessão. */
export async function excluirConta(_: EstadoExclusao, form: FormData): Promise<EstadoExclusao> {
  if (String(form.get("confirmacao") ?? "").trim().toLowerCase() !== "excluir") {
    return { erro: 'Digite "excluir" para confirmar' };
  }
  const r = await enviarApi("/v1/conta", "DELETE");
  if (!r.ok && r.status !== 401) return { erro: r.detalhe ?? "Não foi possível excluir a conta" };
  await signOut({ redirectTo: "/" });
  return {};
}
