/**
 * Estado do screener na URL (Fase 2). A URL é a fonte da verdade: dá para
 * compartilhar e voltar no navegador. Só parâmetros conhecidos são repassados à API.
 */

export const CAMPOS_FAIXA = [
  "preco", "var_1m", "var_12m", "volatilidade_12m", "pos_52s", "dist_mm200", "rsi14",
  "volume_financeiro_20d", "pl", "pvp", "dy_12m", "roe", "margem_liquida", "div_liq_ebitda",
  "valor_mercado",
] as const;

export const ORDENAVEIS = [...CAMPOS_FAIXA, "ticker", "var_1d", "var_ano"] as const;
export const TIPOS = ["acao", "fii", "etf", "bdr"] as const;
export const TENDENCIAS = ["alta", "baixa", "lateral"] as const;

/** Liquidez mínima aplicada quando o usuário não escolhe outra (R$ por dia). */
export const LIQUIDEZ_PADRAO = 100_000;
export const ORDEM_PADRAO = "-volume_financeiro_20d";
export const LIMITE = 50;

type Busca = Record<string, string | string[] | undefined>;

function primeiro(v: string | string[] | undefined): string | undefined {
  return Array.isArray(v) ? v[0] : v;
}

function numero(v: string | undefined): string | undefined {
  if (v === undefined || v.trim() === "") return undefined;
  const n = Number(v.replace(",", "."));
  return Number.isFinite(n) ? String(n) : undefined;
}

/** Converte os searchParams da página em query string para `/v1/screener`. */
export function paramsParaApi(busca: Busca): URLSearchParams {
  const saida = new URLSearchParams();
  for (const campo of CAMPOS_FAIXA) {
    for (const lado of ["min", "max"] as const) {
      const v = numero(primeiro(busca[`${campo}_${lado}`]));
      if (v !== undefined) saida.set(`${campo}_${lado}`, v);
    }
  }
  // Liquidez padrão, a menos que o usuário tenha definido outra ou pedido "todas".
  if (!saida.has("volume_financeiro_20d_min") && primeiro(busca.liquidez) !== "todas") {
    saida.set("volume_financeiro_20d_min", String(LIQUIDEZ_PADRAO));
  }
  const tipos = ([] as string[]).concat(busca.tipo ?? []).filter((t) => (TIPOS as readonly string[]).includes(t));
  for (const t of tipos) saida.append("tipo", t);
  const setor = primeiro(busca.setor)?.trim();
  if (setor) saida.set("setor", setor.slice(0, 80));
  const tendencia = primeiro(busca.tendencia);
  if (tendencia && (TENDENCIAS as readonly string[]).includes(tendencia)) saida.set("tendencia", tendencia);
  saida.set("ordem", ordemValida(primeiro(busca.ordem)));
  const pagina = Number(primeiro(busca.pagina));
  saida.set("pagina", String(Number.isInteger(pagina) && pagina > 0 ? pagina : 1));
  saida.set("limite", String(LIMITE));
  return saida;
}

export function ordemValida(ordem: string | undefined): string {
  if (!ordem) return ORDEM_PADRAO;
  const coluna = ordem.replace(/^-/, "");
  return (ORDENAVEIS as readonly string[]).includes(coluna) ? ordem : ORDEM_PADRAO;
}

/** URL da página com alterações (null remove o parâmetro). Mudar filtro volta à página 1. */
export function urlCom(busca: Busca, mudancas: Record<string, string | null>): string {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(busca)) {
    for (const item of ([] as string[]).concat(v ?? [])) if (item !== "") p.append(k, item);
  }
  for (const [k, v] of Object.entries(mudancas)) {
    p.delete(k);
    if (v !== null) p.set(k, v);
  }
  if (!("pagina" in mudancas)) p.delete("pagina");
  const qs = p.toString();
  return qs ? `/screener?${qs}` : "/screener";
}

/** Clicar no cabeçalho: mesma coluna inverte a direção; coluna nova começa decrescente
 * (ticker começa crescente). */
export function proximaOrdem(atual: string, coluna: string): string {
  if (atual.replace(/^-/, "") === coluna) return atual.startsWith("-") ? coluna : `-${coluna}`;
  return coluna === "ticker" ? "ticker" : `-${coluna}`;
}

export type Preset = { id: string; titulo: string; descricao: string; params: Record<string, string> };

/** Presets descritivos: só combinações de filtros, sem juízo de valor (spec, seção 1). */
export const PRESETS: Preset[] = [
  { id: "maxima-52s", titulo: "Perto da máxima de 52 semanas", descricao: "Posição em 52 semanas acima de 90%", params: { pos_52s_min: "90", ordem: "-pos_52s" } },
  { id: "minima-52s", titulo: "Perto da mínima de 52 semanas", descricao: "Posição em 52 semanas abaixo de 10%", params: { pos_52s_max: "10", ordem: "pos_52s" } },
  { id: "tendencia-alta", titulo: "Tendência de alta", descricao: "Preço acima da MM50, MM50 acima da MM200 e MM200 subindo", params: { tendencia: "alta", ordem: "-var_12m" } },
  { id: "dy-6", titulo: "Dividend yield acima de 6%", descricao: "Proventos de 12 meses acima de 6% do preço", params: { dy_12m_min: "6", ordem: "-dy_12m" } },
  { id: "baixa-volatilidade", titulo: "Baixa volatilidade", descricao: "Volatilidade anualizada abaixo de 25%", params: { volatilidade_12m_max: "25", ordem: "volatilidade_12m" } },
  { id: "mais-negociados", titulo: "Mais negociados", descricao: "Ordenados pela liquidez diária", params: { ordem: "-volume_financeiro_20d" } },
];

export function urlPreset(p: Preset): string {
  return `/screener?${new URLSearchParams(p.params).toString()}`;
}
