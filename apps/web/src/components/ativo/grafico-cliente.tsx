"use client";

import dynamic from "next/dynamic";

// O lightweight-charts só roda no navegador.
export const GraficoCliente = dynamic(() => import("./grafico-ativo").then((m) => m.GraficoAtivo), {
  ssr: false,
  loading: () => <div className="h-[420px] w-full animate-pulse rounded-md bg-muted" />,
});
