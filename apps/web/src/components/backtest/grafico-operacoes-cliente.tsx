"use client";

import dynamic from "next/dynamic";

export const GraficoOperacoesCliente = dynamic(() => import("./grafico-operacoes").then((m) => m.GraficoOperacoes), {
  ssr: false,
  loading: () => <div className="h-80 w-full animate-pulse rounded-md bg-muted" />,
});
