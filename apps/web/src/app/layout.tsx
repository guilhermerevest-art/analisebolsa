import type { Metadata } from "next";

import { AvisoEducacional } from "@/components/aviso-educacional";
import { Cabecalho } from "@/components/cabecalho";
import "./globals.css";

export const metadata: Metadata = {
  title: { default: "analisebolsa", template: "%s · analisebolsa" },
  description: "Análise educacional de ações, FIIs, ETFs e BDRs da B3: gráficos, indicadores, fundamentos e proventos.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pt-BR">
      <body className="flex min-h-dvh flex-col">
        <Cabecalho />
        <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-8">{children}</main>
        <footer className="border-t">
          <div className="mx-auto max-w-6xl px-4 py-6">
            <AvisoEducacional />
          </div>
        </footer>
      </body>
    </html>
  );
}
