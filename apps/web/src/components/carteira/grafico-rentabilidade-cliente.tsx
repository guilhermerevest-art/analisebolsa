"use client";

import dynamic from "next/dynamic";

// O lightweight-charts só roda no navegador.
export const GraficoRentabilidadeCliente = dynamic(() => import("./grafico-rentabilidade").then((m) => m.GraficoRentabilidade), {
  ssr: false,
  loading: () => <div className="h-80 w-full animate-pulse rounded-md bg-muted" />,
});
