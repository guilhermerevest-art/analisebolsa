"use server";

import { revalidatePath } from "next/cache";

import { chamarApi } from "@/lib/api";

const REGEX_TICKER = /^[A-Z0-9]{4,6}$/;

export type ResultadoWatchlist = { naLista: boolean; erro?: string };

/** Adiciona ou remove um ativo da watchlist do usuário logado. */
export async function alterarWatchlist(ticker: string, adicionar: boolean): Promise<ResultadoWatchlist> {
  if (!REGEX_TICKER.test(ticker)) return { naLista: !adicionar, erro: "Ticker inválido" };
  const resp = await chamarApi(`/v1/watchlist/${ticker}`, { method: adicionar ? "PUT" : "DELETE", cache: "no-store" });
  if (!resp.ok) {
    const corpo = (await resp.json().catch(() => ({}))) as { detail?: string };
    const erro = resp.status === 401 ? "Entre na sua conta para usar a watchlist" : (corpo.detail ?? "Não foi possível atualizar a watchlist");
    return { naLista: !adicionar, erro };
  }
  revalidatePath("/watchlist");
  return { naLista: adicionar };
}

/** Versão para formulário (botão de remover na página da watchlist). */
export async function removerDaWatchlist(form: FormData): Promise<void> {
  await alterarWatchlist(String(form.get("ticker") ?? ""), false);
}
