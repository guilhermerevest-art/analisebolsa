import type { components } from "@analisebolsa/api-types";

type S = components["schemas"];
export type AtivoResumo = S["AtivoResumo"];
export type AtivoDetalhe = S["AtivoDetalhe"];
export type PaginaAtivos = S["PaginaAtivos"];
export type Candle = S["Candle"];
export type Cotacoes = S["Cotacoes"];
export type IndicadoresDia = S["IndicadoresDia"];
export type Indicadores = S["Indicadores"];
export type Fundamentos = S["Fundamentos"];
export type FundamentosSnapshot = S["FundamentosSnapshot"];
export type Proventos = S["Proventos"];
export type Destaque = S["Destaque"];
export type Destaques = S["Destaques"];
export type Execucao = S["Execucao"];
export type Execucoes = S["Execucoes"];
export type TipoAtivo = AtivoResumo["tipo"];
