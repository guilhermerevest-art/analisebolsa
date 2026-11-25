/**
 * Regras do BFF: quais caminhos `/api/*` são repassados à API interna (`/v1/*`).
 */
const PREFIXOS_PERMITIDOS = ["ativos", "mercado", "admin"] as const;
const SEGMENTO = /^[A-Za-z0-9_-]{1,40}$/;

/** Converte os segmentos de `/api/...` no caminho da API, ou null se não for permitido. */
export function caminhoApi(segmentos: string[]): string | null {
  if (segmentos.length === 0 || segmentos.length > 4) return null;
  if (!(PREFIXOS_PERMITIDOS as readonly string[]).includes(segmentos[0])) return null;
  if (!segmentos.every((s) => SEGMENTO.test(s))) return null;
  return `/v1/${segmentos.join("/")}`;
}

/** Rotas públicas podem ir para o cache da CDN; admin nunca. */
export function cacheControl(segmentos: string[]): string {
  return segmentos[0] === "admin" ? "private, no-store" : "public, s-maxage=60, stale-while-revalidate=300";
}

/** Tags que o worker pode pedir para revalidar. */
export function tagValida(tag: string): boolean {
  return tag === "mercado" || /^ativo:[A-Z0-9]{4,6}$/.test(tag);
}
