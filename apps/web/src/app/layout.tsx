import type { Metadata } from "next";
import { Bricolage_Grotesque, IBM_Plex_Sans } from "next/font/google";
import Link from "next/link";

import { AvisoEducacional } from "@/components/aviso-educacional";
import { Cabecalho } from "@/components/cabecalho";
import { Marca } from "@/components/marca";
import "./globals.css";

const titulo = Bricolage_Grotesque({ subsets: ["latin", "latin-ext"], variable: "--fonte-titulo", display: "swap" });
const texto = IBM_Plex_Sans({ subsets: ["latin", "latin-ext"], weight: ["400", "500", "600"], variable: "--fonte-texto", display: "swap" });

export const metadata: Metadata = {
  title: { default: "analisebolsa", template: "%s · analisebolsa" },
  description: "Análise educacional de ações, FIIs, ETFs e BDRs da B3: gráficos, indicadores, fundamentos e proventos.",
};

const RODAPE = [
  { titulo: "Analisar", links: [["Screener", "/screener"], ["Backtest", "/backtest"], ["Simulador", "/simulador"], ["Calculadora de posição", "/posicao"]] },
  { titulo: "Sua conta", links: [["Carteira", "/carteira"], ["Watchlist", "/watchlist"], ["Alertas", "/alertas"], ["Criar conta", "/cadastro"]] },
] as const;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pt-BR" className={`${titulo.variable} ${texto.variable}`}>
      <body className="flex min-h-dvh flex-col">
        <Cabecalho />
        <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-8">{children}</main>
        <footer className="mt-16 border-t bg-card">
          <div className="mx-auto grid max-w-6xl gap-10 px-4 py-12 sm:grid-cols-[1.5fr_1fr_1fr]">
            <div className="grid content-start gap-3">
              <Link href="/" className="w-fit">
                <Marca />
              </Link>
              <p className="max-w-xs text-sm text-muted-foreground">
                Gráficos, indicadores e fundamentos dos ativos da B3, atualizados todo fim de pregão.
              </p>
            </div>
            {RODAPE.map((g) => (
              <nav key={g.titulo} aria-label={g.titulo} className="grid content-start gap-2 text-sm">
                <p className="font-medium">{g.titulo}</p>
                {g.links.map(([nome, href]) => (
                  <Link key={href} href={href} className="w-fit text-muted-foreground hover:text-foreground">
                    {nome}
                  </Link>
                ))}
              </nav>
            ))}
          </div>
          <div className="border-t">
            <div className="mx-auto max-w-6xl px-4 py-5">
              <AvisoEducacional />
            </div>
          </div>
        </footer>
      </body>
    </html>
  );
}
