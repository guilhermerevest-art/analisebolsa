import { decimalBr } from "@/lib/validacao";

export type Parametro = { chave: string; rotulo: string; minimo: number; maximo: number; padrao: number };
export type Estrategia = { codigo: string; nome: string; parametros: Parametro[] };

// Mesmos limites da API (dominio/backtest.py).
export const ESTRATEGIAS: Estrategia[] = [
  {
    codigo: "cruzamento_mm",
    nome: "Cruzamento de médias móveis",
    parametros: [
      { chave: "curta", rotulo: "Média curta (pregões)", minimo: 5, maximo: 100, padrao: 20 },
      { chave: "longa", rotulo: "Média longa (pregões)", minimo: 20, maximo: 250, padrao: 100 },
    ],
  },
  {
    codigo: "rsi",
    nome: "IFR (RSI)",
    parametros: [
      { chave: "rsi_periodo", rotulo: "Período do IFR (pregões)", minimo: 2, maximo: 30, padrao: 14 },
      { chave: "rsi_entrada", rotulo: "Entrada com IFR abaixo de", minimo: 5, maximo: 50, padrao: 30 },
      { chave: "rsi_saida", rotulo: "Saída com IFR acima de", minimo: 50, maximo: 95, padrao: 70 },
    ],
  },
  {
    codigo: "macd",
    nome: "Cruzamento do MACD",
    parametros: [
      { chave: "macd_rapida", rotulo: "Média rápida (pregões)", minimo: 5, maximo: 50, padrao: 12 },
      { chave: "macd_lenta", rotulo: "Média lenta (pregões)", minimo: 10, maximo: 100, padrao: 26 },
      { chave: "macd_sinal", rotulo: "Linha de sinal (pregões)", minimo: 3, maximo: 30, padrao: 9 },
    ],
  },
  {
    codigo: "bollinger",
    nome: "Bandas de Bollinger",
    parametros: [
      { chave: "bb_periodo", rotulo: "Período (pregões)", minimo: 10, maximo: 50, padrao: 20 },
      { chave: "bb_desvios", rotulo: "Desvios-padrão", minimo: 1, maximo: 3, padrao: 2 },
    ],
  },
  {
    codigo: "setup_91",
    nome: "Setup 9.1",
    parametros: [{ chave: "mme_periodo", rotulo: "Média exponencial (pregões)", minimo: 5, maximo: 50, padrao: 9 }],
  },
  {
    codigo: "rompimento",
    nome: "Rompimento de máxima",
    parametros: [
      { chave: "n_entrada", rotulo: "Máxima de (pregões)", minimo: 10, maximo: 250, padrao: 55 },
      { chave: "n_saida", rotulo: "Mínima de (pregões)", minimo: 5, maximo: 100, padrao: 20 },
    ],
  },
  { codigo: "buy_and_hold", nome: "Manter o ativo (buy and hold)", parametros: [] },
];

/** Estratégias prontas: atalhos que preenchem a regra e os parâmetros. */
export type Pronta = { id: string; nome: string; resumo: string; estrategia: string; parametros: Record<string, number> };
export const PRONTAS: Pronta[] = [
  { id: "golden-cross", nome: "Golden cross", resumo: "Médias de 50 e 200 pregões", estrategia: "cruzamento_mm", parametros: { curta: 50, longa: 200 } },
  { id: "mm-9-21", nome: "Cruzamento 9/21", resumo: "Médias de 9 e 21 pregões", estrategia: "cruzamento_mm", parametros: { curta: 9, longa: 21 } },
  { id: "ifr2", nome: "IFR2", resumo: "IFR de 2 pregões: entrada abaixo de 10, saída acima de 70", estrategia: "rsi", parametros: { rsi_periodo: 2, rsi_entrada: 10, rsi_saida: 70 } },
  { id: "ifr14", nome: "IFR clássico", resumo: "IFR de 14: entrada abaixo de 30, saída acima de 70", estrategia: "rsi", parametros: { rsi_periodo: 14, rsi_entrada: 30, rsi_saida: 70 } },
  { id: "setup-91", nome: "Setup 9.1", resumo: "Virada da média exponencial de 9", estrategia: "setup_91", parametros: { mme_periodo: 9 } },
  { id: "macd", nome: "MACD", resumo: "MACD 12, 26 e 9", estrategia: "macd", parametros: { macd_rapida: 12, macd_lenta: 26, macd_sinal: 9 } },
  { id: "bollinger", nome: "Bollinger", resumo: "Abaixo da banda de 20 pregões e 2 desvios", estrategia: "bollinger", parametros: { bb_periodo: 20, bb_desvios: 2 } },
  { id: "tartarugas-20", nome: "Tartarugas 20/10", resumo: "Rompimento da máxima de 20, saída na mínima de 10", estrategia: "rompimento", parametros: { n_entrada: 20, n_saida: 10 } },
  { id: "tartarugas-55", nome: "Tartarugas 55/20", resumo: "Rompimento da máxima de 55, saída na mínima de 20", estrategia: "rompimento", parametros: { n_entrada: 55, n_saida: 20 } },
  { id: "buy-and-hold", nome: "Buy and hold", resumo: "Entrada no primeiro pregão, sem saída", estrategia: "buy_and_hold", parametros: {} },
];

export const INICIO_MINIMO_BACKTEST = "2005-01";
const CUSTOS = {
  capital: { padrao: "10.000", minimo: 1000, maximo: 1e9 },
  corretagem: { padrao: "0", minimo: 0, maximo: 100 },
  taxas: { padrao: "0,03", minimo: 0, maximo: 1 },
  deslizamento: { padrao: "0,05", minimo: 0, maximo: 2 },
} as const;
type CampoCusto = keyof typeof CUSTOS;

export type EntradaBacktest = {
  ticker: string;
  estrategia: string;
  inicio: string;
  fim: string;
  parametros: Record<string, string>;
  stop: string;
  cdi: boolean;
} & Record<CampoCusto, string>;
type Erros = Partial<Record<string, string>>;
type Params = Record<string, string | string[] | undefined>;
const ultimo = (v: string | string[] | undefined) => (Array.isArray(v) ? v.at(-1) : v) ?? "";

export const estrategiaPorCodigo = (codigo: string) => ESTRATEGIAS.find((e) => e.codigo === codigo) ?? ESTRATEGIAS[0];

export function valoresPadrao(ticker = ""): EntradaBacktest {
  return {
    ticker,
    estrategia: "cruzamento_mm",
    inicio: "2015-01",
    fim: "",
    parametros: Object.fromEntries(ESTRATEGIAS.flatMap((e) => e.parametros.map((p) => [p.chave, String(p.padrao)]))),
    stop: "",
    cdi: true,
    capital: CUSTOS.capital.padrao,
    corretagem: CUSTOS.corretagem.padrao,
    taxas: CUSTOS.taxas.padrao,
    deslizamento: CUSTOS.deslizamento.padrao,
  };
}

/**
 * Lê o formulário do backtest da URL. `consulta` só vem quando há ativo e início e nada tem erro;
 * os valores já estão no formato da API (só os parâmetros da estratégia escolhida).
 */
export function lerParamsBacktest(params: Params, hoje = new Date()) {
  const padrao = valoresPadrao();
  const texto = (chave: string, fallback: string) => {
    const v = ultimo(params[chave]).trim();
    return params[chave] === undefined ? fallback : v;
  };
  const entrada: EntradaBacktest = {
    ticker: ultimo(params.ticker).trim().toUpperCase(),
    estrategia: estrategiaPorCodigo(ultimo(params.estrategia)).codigo,
    inicio: texto("inicio", padrao.inicio),
    fim: texto("fim", ""),
    parametros: Object.fromEntries(Object.entries(padrao.parametros).map(([k, v]) => [k, texto(k, v)])),
    stop: texto("stop", ""),
    cdi: ultimo(params.cdi) !== "0",
    capital: texto("capital", padrao.capital),
    corretagem: texto("corretagem", padrao.corretagem),
    taxas: texto("taxas", padrao.taxas),
    deslizamento: texto("deslizamento", padrao.deslizamento),
  };
  if (!entrada.ticker) return { entrada, erros: {} as Erros, consulta: null };

  const erros: Erros = {};
  const maximo = mesAtual(hoje);
  const mesValido = (m: string) => /^\d{4}-\d{2}$/.test(m) && m >= INICIO_MINIMO_BACKTEST && m <= maximo;
  if (!/^[A-Z0-9]{4,6}$/.test(entrada.ticker)) erros.ticker = "Ticker inválido";
  if (!mesValido(entrada.inicio)) erros.inicio = `Escolha um mês entre 01/2005 e ${maximo.split("-").reverse().join("/")}`;
  if (entrada.fim && !mesValido(entrada.fim)) erros.fim = "Mês inválido";
  else if (entrada.fim && !erros.inicio && entrada.fim <= entrada.inicio) erros.fim = "O fim precisa vir depois do início";

  const consulta = new URLSearchParams({ ticker: entrada.ticker, estrategia: entrada.estrategia, inicio: `${entrada.inicio}-01` });
  if (entrada.fim) consulta.set("fim", ultimoDiaDoMes(entrada.fim, hoje));

  const estrategia = estrategiaPorCodigo(entrada.estrategia);
  for (const p of estrategia.parametros) {
    const v = entrada.parametros[p.chave];
    const n = Number(v);
    if (!/^\d+$/.test(v) || n < p.minimo || n > p.maximo) erros[p.chave] = `Use um número inteiro de ${p.minimo} a ${p.maximo}`;
    else consulta.set(p.chave, v);
  }
  if (estrategia.codigo === "macd" && !erros.macd_rapida && !erros.macd_lenta && Number(entrada.parametros.macd_rapida) >= Number(entrada.parametros.macd_lenta)) {
    erros.macd_rapida = "A média rápida precisa ser menor que a lenta";
  }
  if (estrategia.codigo === "cruzamento_mm" && !erros.curta && !erros.longa && Number(entrada.parametros.curta) >= Number(entrada.parametros.longa)) {
    erros.curta = "A média curta precisa ser menor que a longa";
  }

  if (entrada.stop) {
    const d = decimalBr(entrada.stop);
    if (d === null || Number(d) < 1 || Number(d) > 5) erros.stop = "Use um múltiplo de 1 a 5";
    else consulta.set("stop_atr", d);
  }
  for (const campo of Object.keys(CUSTOS) as CampoCusto[]) {
    const { minimo, maximo: max } = CUSTOS[campo];
    const d = entrada[campo] ? decimalBr(entrada[campo]) : null;
    if (d === null || Number(d) < minimo || Number(d) > max) erros[campo] = "Valor fora do limite";
    else consulta.set(campo, d);
  }
  consulta.set("cdi_no_caixa", String(entrada.cdi));
  if (Object.keys(erros).length > 0) return { entrada, erros, consulta: null };
  return { entrada, erros, consulta };
}

/** Mês atual (AAAA-MM): o teste pode ir até hoje. */
export function mesAtual(hoje = new Date()): string {
  return hoje.toISOString().slice(0, 7);
}

/** Último dia do mês (AAAA-MM), sem passar de hoje. */
export function ultimoDiaDoMes(mes: string, hoje = new Date()): string {
  const [a, m] = mes.split("-").map(Number);
  const fim = new Date(Date.UTC(a, m, 0)).toISOString().slice(0, 10);
  const hojeIso = hoje.toISOString().slice(0, 10);
  return fim > hojeIso ? hojeIso : fim;
}

/** Retorno total (fração) de cada lado, para a leitura do resultado. */
export type ResumoComparacao = {
  capital: number;
  estrategia: { retorno: number | null; queda: number | null };
  manter: { retorno: number | null; queda: number | null };
  cdi: { retorno: number | null };
};

const reais = (v: number) => v.toLocaleString("pt-BR", { style: "currency", currency: "BRL", maximumFractionDigits: 0 });
const porcento = (v: number) => `${v > 0 ? "+" : v < 0 ? "−" : ""}${Math.abs(v * 100).toLocaleString("pt-BR", { maximumFractionDigits: 1 })}%`;
const comparar = (a: number, b: number) => (Math.abs(a - b) < 0.005 ? "praticamente o mesmo que" : a > b ? "mais que" : "menos que");

/**
 * Frases em linguagem simples sobre o resultado do backtest: quanto o capital teria virado
 * em cada caminho, como a regra se compara aos outros dois e a maior queda. Descrevem o
 * passado; não dizem o que fazer.
 */
export function leituraBacktest(r: ResumoComparacao): string[] {
  const { capital, estrategia: e, manter: m, cdi } = r;
  if (e.retorno === null || m.retorno === null) return [];
  const frases = [
    `Com ${reais(capital)} no início, seguir a regra teria terminado com ${reais(capital * (1 + e.retorno))} (${porcento(e.retorno)}). ` +
      `Manter o ativo o tempo todo teria chegado a ${reais(capital * (1 + m.retorno))} (${porcento(m.retorno)})` +
      (cdi.retorno !== null ? `, e deixar no CDI, a ${reais(capital * (1 + cdi.retorno))} (${porcento(cdi.retorno)}).` : "."),
  ];
  let comparacao = `Nesse histórico, a regra rendeu ${comparar(e.retorno, m.retorno)} manter o ativo`;
  if (cdi.retorno !== null) comparacao += ` e ${comparar(e.retorno, cdi.retorno)} o CDI`;
  frases.push(`${comparacao}.`);
  if (e.queda !== null && m.queda !== null) {
    frases.push(
      `A maior queda no caminho foi de ${porcento(e.queda)} seguindo a regra e de ${porcento(m.queda)} mantendo o ativo. ` +
        "Uma queda menor quer dizer um percurso com sustos menores, mesmo quando o retorno final é menor.",
    );
  }
  frases.push("É um teste sobre o passado, com custos e sem impostos: não mostra o que vai acontecer daqui para frente.");
  return frases;
}
