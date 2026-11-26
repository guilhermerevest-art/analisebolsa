import { decimalBr } from "@/lib/validacao";

export type EntradaPosicao = {
  ticker: string;
  capital: string;
  risco: string;
  entrada: string;
  modo: "preco" | "atr";
  stop: string;
  atr: string;
  lote: "100" | "1";
  concentracao: string;
};
type Params = Record<string, string | string[] | undefined>;
const ultimo = (v: string | string[] | undefined) => (Array.isArray(v) ? v.at(-1) : v) ?? "";

export const PADRAO_POSICAO: EntradaPosicao = {
  ticker: "",
  capital: "",
  risco: "1",
  entrada: "",
  modo: "preco",
  stop: "",
  atr: "2",
  lote: "100",
  concentracao: "25",
};

const LIMITES = {
  capital: [1, 1e10],
  risco: [0.1, 5],
  entrada: [0.01, 1e6],
  stop: [0.01, 1e6],
  atr: [0.5, 5],
  concentracao: [1, 100],
} as const;

/**
 * Lê a calculadora da URL. `consulta` vem quando há capital e preço de entrada (ou um ativo, que
 * preenche o último fechamento) e nenhum erro. Com ticker e sem capital, só preenche o ativo.
 */
export function lerParamsPosicao(params: Params) {
  const texto = (k: keyof EntradaPosicao) => (params[k] === undefined ? PADRAO_POSICAO[k] : ultimo(params[k]).trim());
  const entrada: EntradaPosicao = {
    ticker: ultimo(params.ticker).trim().toUpperCase(),
    capital: texto("capital"),
    risco: texto("risco"),
    entrada: texto("entrada"),
    modo: ultimo(params.modo) === "atr" ? "atr" : "preco",
    stop: texto("stop"),
    atr: texto("atr"),
    lote: ultimo(params.lote) === "1" ? "1" : "100",
    concentracao: texto("concentracao"),
  };
  const erros: Partial<Record<keyof EntradaPosicao, string>> = {};
  if (!entrada.capital) return { entrada, erros, consulta: null };

  if (entrada.ticker && !/^[A-Z0-9]{4,6}$/.test(entrada.ticker)) erros.ticker = "Ticker inválido";
  const consulta = new URLSearchParams({ lote: entrada.lote });
  if (entrada.ticker) consulta.set("ticker", entrada.ticker);

  const numero = (campo: keyof typeof LIMITES, chaveApi: string, obrigatorio: boolean) => {
    const v = entrada[campo];
    if (!v) {
      if (obrigatorio) erros[campo] = "Obrigatório";
      return;
    }
    const d = decimalBr(v);
    const [min, max] = LIMITES[campo];
    if (d === null || Number(d) < min || Number(d) > max) erros[campo] = "Valor fora do limite";
    else consulta.set(chaveApi, d);
  };
  numero("capital", "capital", true);
  numero("risco", "risco", true);
  numero("concentracao", "concentracao", true);
  numero("entrada", "entrada", !entrada.ticker);
  if (entrada.modo === "atr") {
    if (!entrada.ticker) erros.atr = "O stop por ATR precisa de um ativo";
    else numero("atr", "atr_mult", true);
  } else {
    numero("stop", "stop", true);
  }
  if (!erros.entrada && !erros.stop && entrada.modo === "preco" && entrada.entrada && entrada.stop) {
    if (Number(decimalBr(entrada.stop)) >= Number(decimalBr(entrada.entrada))) erros.stop = "O stop precisa ficar abaixo da entrada";
  }
  return Object.keys(erros).length > 0 ? { entrada, erros, consulta: null } : { entrada, erros, consulta };
}
