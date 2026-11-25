import { decimalBr } from "@/lib/validacao";

export type EntradaSimulador = { ticker: string; inicio: string; inicial: string; mensal: string; reinvestir: boolean };
type Erros = Partial<Record<keyof EntradaSimulador | "aportes", string>>;

export const INICIO_MINIMO = "2005-01";
const LIMITES = { inicial: 1e9, mensal: 1e8 } as const;

type Params = Record<string, string | string[] | undefined>;
const ultimo = (v: string | string[] | undefined) => (Array.isArray(v) ? v.at(-1) : v) ?? "";

/** Último mês aceito como início: o anterior ao atual. */
export function mesMaximo(hoje = new Date()): string {
  const d = new Date(Date.UTC(hoje.getUTCFullYear(), hoje.getUTCMonth() - 1, 1));
  return d.toISOString().slice(0, 7);
}

/**
 * Lê o formulário do simulador da URL. `consulta` vem preenchida só quando o formulário foi
 * enviado (há `inicio`) e não tem erros; os valores já estão no formato da API.
 */
export function lerParamsSimulador(params: Params, hoje = new Date()) {
  const entrada: EntradaSimulador = {
    ticker: ultimo(params.ticker).trim().toUpperCase(),
    inicio: ultimo(params.inicio).trim(),
    inicial: ultimo(params.inicial).trim(),
    mensal: ultimo(params.mensal).trim(),
    reinvestir: ultimo(params.reinvestir) !== "0",
  };
  if (!entrada.inicio) return { entrada, erros: {} as Erros, consulta: null };

  const erros: Erros = {};
  if (entrada.ticker && !/^[A-Z0-9]{4,6}$/.test(entrada.ticker)) erros.ticker = "Ticker inválido";
  if (!/^\d{4}-\d{2}$/.test(entrada.inicio) || entrada.inicio < INICIO_MINIMO || entrada.inicio > mesMaximo(hoje)) {
    erros.inicio = `Escolha um mês entre 01/2005 e ${mesMaximo(hoje).split("-").reverse().join("/")}`;
  }
  const valores = { inicial: "0", mensal: "0" };
  for (const campo of ["inicial", "mensal"] as const) {
    if (!entrada[campo]) continue;
    const d = decimalBr(entrada[campo]);
    if (d === null || (d.split(".")[1] ?? "").length > 2) erros[campo] = "Valor inválido";
    else if (Number(d) > LIMITES[campo]) erros[campo] = "Valor acima do limite";
    else valores[campo] = d;
  }
  if (!erros.inicial && !erros.mensal && Number(valores.inicial) <= 0 && Number(valores.mensal) <= 0) {
    erros.aportes = "Informe um aporte inicial ou mensal";
  }
  if (Object.keys(erros).length > 0) return { entrada, erros, consulta: null };

  const consulta = new URLSearchParams({
    inicio: `${entrada.inicio}-01`,
    aporte_inicial: valores.inicial,
    aporte_mensal: valores.mensal,
    reinvestir: String(entrada.reinvestir),
  });
  if (entrada.ticker) consulta.set("ticker", entrada.ticker);
  return { entrada, erros, consulta };
}

/** Último ponto de cada ano. */
export function fimDeCadaAno<T extends { data: string }>(pontos: T[]): T[] {
  return pontos.filter((p, i) => i === pontos.length - 1 || pontos[i + 1].data.slice(0, 4) !== p.data.slice(0, 4));
}
