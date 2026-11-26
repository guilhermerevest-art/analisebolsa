"use client";

import { GraficoLinhas, type SerieLinha } from "@/components/graficos/grafico-linhas";
import type { RentabilidadeCarteira } from "@/lib/tipos-api";

// Paleta validada (scripts/validate_palette.js do dataviz) no claro e no escuro.
const SERIES: SerieLinha[] = [
  { chave: "carteira", rotulo: "Carteira", claro: "#2f6bff", escuro: "#5a88ff" },
  { chave: "cdi", rotulo: "CDI", claro: "#d97706", escuro: "#d97706" },
  { chave: "ibov", rotulo: "Ibovespa", claro: "#9333ea", escuro: "#a855f7" },
  { chave: "dolar", rotulo: "Dólar", claro: "#0e9f8e", escuro: "#2dd4bf" },
];

export function GraficoRentabilidade({ dados }: { dados: RentabilidadeCarteira }) {
  return (
    <GraficoLinhas
      pontos={dados.pontos}
      series={SERIES}
      formato="pct"
      rotuloAcessivel="Rentabilidade acumulada da carteira, do CDI, do Ibovespa e do dólar no mesmo período"
    />
  );
}
