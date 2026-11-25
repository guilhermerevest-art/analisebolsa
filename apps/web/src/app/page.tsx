import Link from "next/link";

import { Button } from "@/components/ui/button";

// A landing completa (busca, faixa de cotações e funcionalidades) entra na etapa 4.
export default function Inicio() {
  return (
    <section className="mx-auto flex max-w-2xl flex-col items-center gap-6 py-16 text-center">
      <h1 className="text-4xl font-bold tracking-tight sm:text-5xl">Entenda os ativos da B3</h1>
      <p className="text-lg text-muted-foreground">
        Gráficos, indicadores técnicos, fundamentos e proventos de ações, FIIs, ETFs e BDRs, atualizados
        todo fim de pregão.
      </p>
      <Button asChild size="lg">
        <Link href="/cadastro">Criar conta grátis</Link>
      </Button>
    </section>
  );
}
