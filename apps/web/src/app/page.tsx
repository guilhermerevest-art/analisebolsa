import { BarChart3, Bell, Briefcase, Calculator, CandlestickChart, Coins, Filter, FlaskConical, Lightbulb, Target } from "lucide-react";
import Link from "next/link";

import { BuscaGlobal } from "@/components/busca-global";
import { SinaisDeHoje } from "@/components/landing/sinais";
import { BentoCard, BentoGrid } from "@/components/magic/bento-grid";
import { Marquee } from "@/components/magic/marquee";
import { Button } from "@/components/ui/button";
import { lerDestaques, lerSinais } from "@/lib/dados";
import { classeVariacao, formatarPct, formatarPreco } from "@/lib/formato";
import type { Destaque } from "@/lib/tipos-api";
import { cn } from "@/lib/utils";

export const revalidate = 300;

const FUNCIONALIDADES = [
  { titulo: "Gráfico e indicadores", descricao: "Candles com médias móveis, Bollinger, RSI e MACD.", icone: <CandlestickChart />, classe: "md:col-span-2" },
  { titulo: "Fundamentos", descricao: "P/L, P/VP, ROE, margem, dívida e mais.", icone: <BarChart3 /> },
  { titulo: "Proventos", descricao: "Histórico de dividendos, JCP e rendimentos, com DY por ano.", icone: <Coins /> },
  { titulo: "Insights", descricao: "Leitura educacional dos sinais técnicos de cada ativo, na aba Análise.", icone: <Lightbulb /> },
  { titulo: "Cenários", descricao: "Suportes, resistências e cenários condicionais de alta, lateral e baixa.", icone: <Target /> },
  { titulo: "Screener", descricao: "Filtre ativos por indicadores e fundamentos.", icone: <Filter />, href: "/screener", classe: "md:col-span-2" },
  { titulo: "Carteira", descricao: "Posições, preço médio, proventos recebidos e alocação.", icone: <Briefcase />, href: "/carteira" },
  { titulo: "Simulador", descricao: "Aportes mensais com reinvestimento, comparados ao CDI e ao IPCA.", icone: <Calculator />, href: "/simulador" },
  { titulo: "Backtest", descricao: "Golden cross, IFR2, Setup 9.1, MACD e outras regras testadas no histórico, com custos.", icone: <FlaskConical />, href: "/backtest", classe: "md:col-span-2" },
  { titulo: "Alertas", descricao: "Avisos por e-mail quando um ativo cruza um preço, varia muito no dia ou gera um sinal.", icone: <Bell />, href: "/alertas" },
];

function ItemFaixa({ d }: { d: Destaque }) {
  return (
    <Link href={`/ativo/${d.ticker}`} className="flex items-center gap-2 whitespace-nowrap text-sm hover:underline">
      <span className="font-semibold">{d.ticker}</span>
      <span className="tabular-nums text-muted-foreground">{formatarPreco(d.fechamento)}</span>
      <span className={cn("tabular-nums font-medium", classeVariacao(d.variacao))}>{formatarPct(d.variacao)}</span>
    </Link>
  );
}

export default async function Inicio() {
  const [destaques, sinais] = await Promise.all([lerDestaques(), lerSinais()]);
  const faixa = destaques ? [...destaques.altas, ...destaques.baixas] : [];
  return (
    <div className="grid grid-cols-[minmax(0,1fr)] gap-16">
      <section className="mx-auto flex max-w-2xl flex-col items-center gap-6 pt-10 text-center">
        <h1 className="text-4xl font-bold tracking-tight sm:text-5xl">Entenda os ativos da B3</h1>
        <p className="text-lg text-muted-foreground">
          Gráficos, indicadores técnicos, fundamentos e proventos de ações, FIIs, ETFs e BDRs, atualizados todo fim de pregão.
        </p>
        <BuscaGlobal variante="hero" />
      </section>

      {faixa.length > 0 && (
        <section aria-label="Maiores altas e baixas do último pregão" className="-mx-4 overflow-hidden border-y py-3">
          <Marquee>
            {faixa.map((d) => (
              <ItemFaixa key={d.ticker} d={d} />
            ))}
          </Marquee>
        </section>
      )}

      {sinais && <SinaisDeHoje dados={sinais} />}

      <section aria-labelledby="funcionalidades">
        <h2 id="funcionalidades" className="mb-6 text-2xl font-semibold tracking-tight">
          O que você encontra aqui
        </h2>
        <BentoGrid>
          {FUNCIONALIDADES.map((f) => (
            <BentoCard key={f.titulo} titulo={f.titulo} descricao={f.descricao} icone={f.icone} href={"href" in f ? f.href : undefined} className={f.classe} />
          ))}
        </BentoGrid>
      </section>

      <section className="flex flex-col items-center gap-4 rounded-xl border bg-card p-10 text-center">
        <h2 className="text-2xl font-semibold tracking-tight">Crie sua conta grátis</h2>
        <p className="max-w-md text-muted-foreground">A conta vai guardar sua carteira, sua lista de acompanhamento e seus alertas.</p>
        <Button asChild size="lg">
          <Link href="/cadastro">Criar conta</Link>
        </Button>
      </section>
    </div>
  );
}
