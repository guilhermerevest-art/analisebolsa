"use client";

import { GraficoLinhas, type SerieLinha } from "@/components/graficos/grafico-linhas";
import type { RentabilidadeCarteira } from "@/lib/tipos-api";

// Paleta validada (scripts/validate_palette.js do dataviz) no claro e no escuro.
const SERIES: SerieLinha[] = [
  { chave: "carteira", rotulo: "Carteira", claro: "#1f51ff", escuro: "#5b87ff" },
  { chave: "cdi", rotulo: "CDI", claro: "#d97706", escuro: "#d97706" },
  { chave: "ibov", rotulo: "Ibovespa", claro: "#9333ea", escuro: "#a855f7" },
];

export function GraficoRentabilidade({ dados }: { dados: RentabilidadeCarteira }) {
  return (
    <GraficoLinhas
      pontos={dados.pontos}
      series={SERIES}
      formato="pct"
      rotuloAcessivel="Rentabilidade acumulada da carteira, do CDI e do Ibovespa no mesmo período"
    />
  );
}
