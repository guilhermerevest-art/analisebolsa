import "server-only";

import { env } from "@/lib/env";
import type { AtivoDetalhe, Destaques, Fundamentos, PaginaAtivos, Proventos } from "@/lib/tipos-api";

const UMA_HORA = 3600;

/**
 * Leitura pública da API para páginas renderizadas no servidor, com cache do
 * Next.js. O worker renova as tags no fim do EOD (/api/internal/revalidate).
 */
async function lerApi<T>(caminho: string, tags: string[], revalidate = UMA_HORA): Promise<T | null> {
  const resp = await fetch(`${env("API_INTERNAL_URL").replace(/\/$/, "")}${caminho}`, {
    headers: { Accept: "application/json" },
    next: { revalidate, tags },
  });
  if (resp.status === 404) return null;
  if (!resp.ok) throw new Error(`API ${resp.status} em ${caminho}`);
  return (await resp.json()) as T;
}

export const lerAtivo = (t: string) => lerApi<AtivoDetalhe>(`/v1/ativos/${t}`, [`ativo:${t}`]);
export const lerFundamentos = (t: string) => lerApi<Fundamentos>(`/v1/ativos/${t}/fundamentos`, [`ativo:${t}`]);
export const lerProventos = (t: string) => lerApi<Proventos>(`/v1/ativos/${t}/proventos`, [`ativo:${t}`]);

export async function lerDestaques(): Promise<Destaques | null> {
  try {
    return await lerApi<Destaques>("/v1/mercado/destaques?limite=12", ["mercado"], 300);
  } catch {
    return null; // a landing continua de pé sem a faixa de cotações
  }
}

/** Todos os tickers ativos, para o sitemap. */
export async function lerTodosTickers(): Promise<string[]> {
  const tickers: string[] = [];
  for (let pagina = 1; pagina <= 100; pagina++) {
    const r = await lerApi<PaginaAtivos>(`/v1/ativos?limite=100&pagina=${pagina}`, ["mercado"], 86400);
    if (!r || r.itens.length === 0) break;
    tickers.push(...r.itens.map((a) => a.ticker));
    if (tickers.length >= r.total) break;
  }
  return tickers;
}
