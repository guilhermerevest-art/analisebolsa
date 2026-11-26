import type { Metadata } from "next";
import Link from "next/link";

import { CATEGORIAS, GLOSSARIO, type Termo } from "@/lib/glossario";

export const metadata: Metadata = {
  title: "Glossário",
  description: "Os termos de ações, FIIs, indicadores, fundamentos, risco e imposto de renda explicados em linguagem simples.",
};

const ancora = (categoria: string) =>
  categoria
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .replace(/[^a-z]+/g, "-");

export default function Glossario() {
  const termos = Object.entries(GLOSSARIO) as [string, Termo][];
  return (
    <div className="grid grid-cols-[minmax(0,1fr)] gap-10">
      <div className="grid gap-4">
        <h1 className="text-3xl font-semibold tracking-tight">Glossário</h1>
        <p className="max-w-2xl text-muted-foreground">
          Os termos que aparecem no site, explicados sem jargão. Nas páginas, o ícone de interrogação ao lado de um termo mostra a mesma explicação.
        </p>
        <nav aria-label="Categorias" className="flex flex-wrap gap-2">
          {CATEGORIAS.map((c) => (
            <a key={c} href={`#${ancora(c)}`} className="rounded-full border bg-card px-3 py-1 text-sm transition-colors hover:border-azul hover:text-azul">
              {c}
            </a>
          ))}
        </nav>
      </div>

      {CATEGORIAS.map((c) => (
        <section key={c} id={ancora(c)} aria-labelledby={`titulo-${ancora(c)}`} className="grid scroll-mt-24 gap-4">
          <h2 id={`titulo-${ancora(c)}`} className="text-xl font-semibold">
            {c}
          </h2>
          <dl className="grid gap-3 md:grid-cols-2">
            {termos
              .filter(([, t]) => t.categoria === c)
              .map(([chave, t]) => (
                <div key={chave} id={chave} className="grid scroll-mt-24 content-start gap-1 rounded-xl border bg-card p-4">
                  <dt className="font-semibold">{t.titulo}</dt>
                  <dd className="text-sm leading-relaxed text-muted-foreground">{t.curto}</dd>
                  {t.longo && <dd className="text-sm leading-relaxed text-muted-foreground">{t.longo}</dd>}
                </div>
              ))}
          </dl>
        </section>
      ))}

      <p className="text-sm text-muted-foreground">
        Sentiu falta de algum termo? As páginas de{" "}
        <Link href="/backtest" className="text-azul underline-offset-2 hover:underline">
          backtest
        </Link>{" "}
        e de{" "}
        <Link href="/carteira/imposto" className="text-azul underline-offset-2 hover:underline">
          imposto
        </Link>{" "}
        também explicam como cada conta é feita.
      </p>
    </div>
  );
}
