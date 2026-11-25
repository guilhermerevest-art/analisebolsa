const brl = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });
const brlPequeno = new Intl.NumberFormat("pt-BR", {
  style: "currency",
  currency: "BRL",
  minimumFractionDigits: 2,
  maximumFractionDigits: 4,
});
const compacto = new Intl.NumberFormat("pt-BR", { notation: "compact", maximumFractionDigits: 1 });
const decimal = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 2 });

/** Preço em reais. A API manda string decimal ("38.63"). */
export function formatarPreco(valor: string | number | null | undefined): string {
  if (valor === null || valor === undefined || valor === "") return "—";
  const n = Number(valor);
  if (!Number.isFinite(n)) return "—";
  return (Math.abs(n) < 1 ? brlPequeno : brl).format(n);
}

/** Variação percentual com sinal: "+1,23%" / "−0,45%". */
export function formatarPct(valor: number | null | undefined): string {
  if (valor === null || valor === undefined || !Number.isFinite(valor)) return "—";
  const abs = decimal.format(Math.abs(valor));
  if (valor > 0) return `+${abs}%`;
  if (valor < 0) return `−${abs}%`;
  return `${abs}%`;
}

export function formatarNumero(valor: number | string | null | undefined, casas = 2): string {
  if (valor === null || valor === undefined || valor === "") return "—";
  const n = Number(valor);
  if (!Number.isFinite(n)) return "—";
  return new Intl.NumberFormat("pt-BR", { maximumFractionDigits: casas }).format(n);
}

export function formatarCompacto(valor: number | string | null | undefined): string {
  if (valor === null || valor === undefined || valor === "") return "—";
  const n = Number(valor);
  return Number.isFinite(n) ? compacto.format(n) : "—";
}

/** "2025-06-04" -> "04/06/2025" sem passar por fuso horário. */
export function formatarData(iso: string | null | undefined): string {
  if (!iso) return "—";
  const [a, m, d] = iso.slice(0, 10).split("-");
  return a && m && d ? `${d}/${m}/${a}` : "—";
}

export function classeVariacao(valor: number | null | undefined): string {
  if (!valor) return "text-muted-foreground";
  return valor > 0 ? "text-positivo" : "text-destructive";
}

export const NOMES_TIPO = { acao: "Ação", fii: "FII", etf: "ETF", bdr: "BDR" } as const;

export const NOMES_PROVENTO: Record<string, string> = {
  dividendo: "Dividendo",
  jcp: "JCP",
  rendimento: "Rendimento",
  bonificacao: "Bonificação",
  desdobramento: "Desdobramento",
  grupamento: "Grupamento",
};
