import "server-only";

import { cabecalhosApi, env } from "@/lib/env";
import type { AnaliseAtivo, Backtest, Simulacao, SinaisDoDia, AtivoDetalhe, CamposScreener, Destaques, Fundamentos, PaginaAtivos, PaginaScreener, Proventos } from "@/lib/tipos-api";

const UMA_HORA = 3600;

/**
 * Leitura pública da API para páginas renderizadas no servidor, com cache do
 * Next.js. O worker renova as tags no fim do EOD (/api/internal/revalidate).
 */
async function lerApi<T>(caminho: string, tags: string[], revalidate = UMA_HORA): Promise<T | null> {
  const resp = await fetch(`${env("API_INTERNAL_URL").replace(/\/$/, "")}${caminho}`, {
    headers: cabecalhosApi(),
    next: { revalidate, tags },
  });
  if (resp.status === 404) return null;
  if (!resp.ok) throw new Error(`API ${resp.status} em ${caminho}`);
  return (await resp.json()) as T;
}

export const lerAtivo = (t: string) => lerApi<AtivoDetalhe>(`/v1/ativos/${t}`, [`ativo:${t}`]);
export const lerFundamentos = (t: string) => lerApi<Fundamentos>(`/v1/ativos/${t}/fundamentos`, [`ativo:${t}`]);
export const lerAnalise = (t: string) =>
  lerApi<AnaliseAtivo>(`/v1/ativos/${t}/analise`, [`ativo:${t}`]).catch(() => null);
export const lerProventos = (t: string) => lerApi<Proventos>(`/v1/ativos/${t}/proventos`, [`ativo:${t}`]);

export async function lerDestaques(): Promise<Destaques | null> {
  try {
    return await lerApi<Destaques>("/v1/mercado/destaques?limite=12", ["mercado"], 300);
  } catch {
    return null; // a landing continua de pé sem a faixa de cotações
  }
}

export async function lerSinais(): Promise<SinaisDoDia | null> {
  try {
    return await lerApi<SinaisDoDia>("/v1/mercado/sinais?exemplos=4", ["mercado"], 300);
  } catch {
    return null;
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

/** Screener: a query string já vem filtrada por `paramsParaApi`. */
export const lerScreener = (qs: URLSearchParams) =>
  lerApi<PaginaScreener>(`/v1/screener?${qs.toString()}`, ["mercado"], 300);

export const lerCamposScreener = () => lerApi<CamposScreener>("/v1/screener/campos", ["mercado"], UMA_HORA);

/** Simulador: público e cacheado por URL; a query string já vem validada por `lerParamsSimulador`. */
export const lerSimulacao = (qs: URLSearchParams) => lerApi<Simulacao>(`/v1/simulador?${qs.toString()}`, ["mercado"], UMA_HORA);

/** Backtest: 422 traz a mensagem da API (ex.: histórico curto); 404 é ativo inexistente. */
export async function lerBacktest(qs: URLSearchParams): Promise<{ dados: Backtest } | { erro: string; status: number }> {
  const resp = await fetch(`${env("API_INTERNAL_URL").replace(/\/$/, "")}/v1/backtest?${qs.toString()}`, {
    headers: cabecalhosApi(),
    next: { revalidate: UMA_HORA, tags: ["mercado"] },
  });
  if (resp.ok) return { dados: (await resp.json()) as Backtest };
  if (resp.status === 404 || resp.status === 422) {
    const corpo = (await resp.json().catch(() => ({}))) as { detail?: unknown };
    return { erro: typeof corpo.detail === "string" ? corpo.detail : "Não foi possível rodar o teste", status: resp.status };
  }
  throw new Error(`API ${resp.status} em /v1/backtest`);
}
