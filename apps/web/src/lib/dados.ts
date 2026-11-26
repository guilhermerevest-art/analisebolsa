import "server-only";

import { cabecalhosApi, env } from "@/lib/env";
import type { AnaliseAtivo, Indice, Backtest, Posicao, Simulacao, SinaisDoDia, AtivoDetalhe, CamposScreener, Destaques, Fundamentos, PaginaAtivos, PaginaScreener, Proventos } from "@/lib/tipos-api";

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

/** Ibovespa dos últimos 12 meses, para o gráfico da landing. */
export async function lerIbovespa(): Promise<Indice | null> {
  try {
    return await lerApi<Indice>("/v1/indices/ibov", ["mercado"], 300);
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

/** Leitura que devolve a mensagem da API em 404 e 422 (ex.: histórico curto, stop inválido). */
async function lerComErro<T>(caminho: string): Promise<{ dados: T } | { erro: string; status: number }> {
  const resp = await fetch(`${env("API_INTERNAL_URL").replace(/\/$/, "")}${caminho}`, {
    headers: cabecalhosApi(),
    next: { revalidate: UMA_HORA, tags: ["mercado"] },
  });
  if (resp.ok) return { dados: (await resp.json()) as T };
  if (resp.status === 404 || resp.status === 422) {
    const corpo = (await resp.json().catch(() => ({}))) as { detail?: unknown };
    const detalhe = typeof corpo.detail === "string" && corpo.detail !== "Parâmetros inválidos" ? corpo.detail : "Confira os valores informados";
    return { erro: detalhe, status: resp.status };
  }
  throw new Error(`API ${resp.status} em ${caminho.split("?")[0]}`);
}

export const lerBacktest = (qs: URLSearchParams) => lerComErro<Backtest>(`/v1/backtest?${qs.toString()}`);
export const lerPosicao = (qs: URLSearchParams) => lerComErro<Posicao>(`/v1/posicao?${qs.toString()}`);
