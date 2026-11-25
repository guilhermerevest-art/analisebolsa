"use client";

import dynamic from "next/dynamic";

// O lightweight-charts só roda no navegador.
export const GraficoLinhasCliente = dynamic(() => import("./grafico-linhas").then((m) => m.GraficoLinhas), {
  ssr: false,
  loading: () => <div className="h-80 w-full animate-pulse rounded-md bg-muted" />,
});
