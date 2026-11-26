import { BarChart3, Bell, Briefcase, Calculator, CandlestickChart, Coins, Filter, FlaskConical, Lightbulb, Scale, Star } from "lucide-react";
import Link from "next/link";

import { BuscaGlobal } from "@/components/busca-global";
import { PainelIbovespa } from "@/components/landing/painel-ibovespa";
import { SinaisDeHoje } from "@/components/landing/sinais";
import { Marquee } from "@/components/magic/marquee";
import { Button } from "@/components/ui/button";
import { FaixaMercado } from "@/components/mercado/faixa-mercado";
import { lerDestaques, lerIbovespa, lerIndicadores, lerSinais } from "@/lib/dados";
import { classeVariacao, formatarPct, formatarPreco } from "@/lib/formato";
import type { Destaque } from "@/lib/tipos-api";
import { cn } from "@/lib/utils";

export const revalidate = 300;

const EXEMPLOS = ["PETR4", "VALE3", "ITUB4", "HGLG11", "BOVA11"];

type Item = { titulo: string; descricao: string; icone: React.ReactNode; href?: string };

const GRUPOS: { titulo: string; descricao: string; itens: Item[] }[] = [
  {
    titulo: "Analisar um ativo",
    descricao: "Tudo na página de cada ticker.",
    itens: [
      { titulo: "Gráfico e indicadores", descricao: "Candles com médias móveis, Bollinger, RSI e MACD.", icone: <CandlestickChart />, href: "/ativo/PETR4" },
      { titulo: "Fundamentos", descricao: "P/L, P/VP, ROE, margem, dívida e mais.", icone: <BarChart3 /> },
      { titulo: "Proventos", descricao: "Dividendos, JCP e rendimentos, com DY por ano.", icone: <Coins /> },
      { titulo: "Análise e cenários", descricao: "Leitura dos sinais técnicos, suportes, resistências e cenários de alta, lateral e baixa.", icone: <Lightbulb /> },
    ],
  },
  {
    titulo: "Filtrar e testar",
    descricao: "Para comparar ativos e regras.",
    itens: [
      { titulo: "Screener", descricao: "Filtre por indicadores e fundamentos, ou use filtros prontos.", icone: <Filter />, href: "/screener" },
      { titulo: "Backtest", descricao: "Golden cross, IFR2, Setup 9.1, MACD e outras regras no histórico, com custos.", icone: <FlaskConical />, href: "/backtest" },
      { titulo: "Simulador", descricao: "Aportes mensais com reinvestimento, comparados ao CDI e ao IPCA.", icone: <Calculator />, href: "/simulador" },
    ],
  },
  {
    titulo: "Acompanhar",
    descricao: "Com uma conta grátis.",
    itens: [
      { titulo: "Carteira", descricao: "Posições, preço médio, proventos recebidos e alocação.", icone: <Briefcase />, href: "/carteira" },
      { titulo: "Watchlist", descricao: "Os ativos que você acompanha, num lugar só.", icone: <Star />, href: "/watchlist" },
      { titulo: "Alertas", descricao: "Notificação no celular ou WhatsApp quando um ativo cruza um preço, varia muito ou gera um sinal.", icone: <Bell />, href: "/alertas" },
      { titulo: "Calculadora de posição", descricao: "Quantidade pelo risco até o stop, manual ou por ATR.", icone: <Scale />, href: "/posicao" },
    ],
  },
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

/** Sem a série do Ibovespa, o hero mostra as maiores altas e baixas do pregão. */
function PainelDestaques({ altas, baixas }: { altas: Destaque[]; baixas: Destaque[] }) {
  const lista = (titulo: string, itens: Destaque[]) => (
    <div className="grid content-start gap-1">
      <p className="mb-1 text-sm text-muted-foreground">{titulo}</p>
      {itens.slice(0, 5).map((d) => (
        <Link key={d.ticker} href={`/ativo/${d.ticker}`} className="-mx-2 flex items-center justify-between rounded-md px-2 py-1.5 text-sm hover:bg-muted">
          <span className="font-semibold">{d.ticker}</span>
          <span className={cn("tabular-nums font-medium", classeVariacao(d.variacao))}>{formatarPct(d.variacao)}</span>
        </Link>
      ))}
    </div>
  );
  return (
    <div className="grid gap-6 rounded-2xl border bg-card p-6 sm:grid-cols-2">
      {lista("Maiores altas", altas)}
      {lista("Maiores baixas", baixas)}
    </div>
  );
}

function LinhaFuncionalidade({ item }: { item: Item }) {
  const conteudo = (
    <>
      <span className="mt-0.5 flex size-9 shrink-0 items-center justify-center rounded-lg bg-accent text-azul [&_svg]:size-[18px]">{item.icone}</span>
      <span className="grid gap-0.5">
        <span className="font-medium group-hover:text-azul">{item.titulo}</span>
        <span className="text-sm text-muted-foreground">{item.descricao}</span>
      </span>
    </>
  );
  const classe = "group -mx-3 flex gap-3 rounded-lg px-3 py-3";
  return item.href ? (
    <Link href={item.href} className={cn(classe, "transition-colors hover:bg-muted")}>
      {conteudo}
    </Link>
  ) : (
    <div className={classe}>{conteudo}</div>
  );
}

export default async function Inicio() {
  const [destaques, sinais, ibov, indicadores] = await Promise.all([lerDestaques(), lerSinais(), lerIbovespa(), lerIndicadores()]);
  const faixa = destaques ? [...destaques.altas, ...destaques.baixas] : [];
  const temPainel = Boolean((ibov && ibov.pontos.length > 1) || faixa.length > 0);

  return (
    <div className="grid grid-cols-[minmax(0,1fr)] gap-20">
      <section className={cn("grid grid-cols-[minmax(0,1fr)] items-center gap-10 pt-6 sm:pt-12", temPainel && "lg:grid-cols-[minmax(0,1fr)_minmax(0,1.05fr)]")}>
        <div className="grid grid-cols-[minmax(0,1fr)] gap-6">
          <h1 className="max-w-xl text-4xl font-semibold leading-[1.05] tracking-tight sm:text-6xl">Entenda os ativos da B3 antes de investir</h1>
          <p className="max-w-lg text-lg text-muted-foreground">
            Gráficos, indicadores técnicos, fundamentos e proventos de ações, FIIs, ETFs e BDRs, atualizados todo fim de pregão.
          </p>
          <BuscaGlobal variante="hero" />
          <div className="flex flex-wrap items-center gap-2 text-sm">
            <span className="text-muted-foreground">Comece por</span>
            {EXEMPLOS.map((t) => (
              <Link key={t} href={`/ativo/${t}`} className="rounded-md border bg-card px-2.5 py-1 font-medium transition-colors hover:border-azul hover:text-azul">
                {t}
              </Link>
            ))}
          </div>
        </div>
        {ibov && ibov.pontos.length > 1 ? (
          <PainelIbovespa indice={ibov} />
        ) : (
          destaques && faixa.length > 0 && <PainelDestaques altas={destaques.altas} baixas={destaques.baixas} />
        )}
      </section>

      {faixa.length > 0 && (
        <section aria-label="Maiores altas e baixas do último pregão" className="-my-8 overflow-hidden rounded-xl border bg-card py-3.5">
          <Marquee>
            {faixa.map((d) => (
              <ItemFaixa key={d.ticker} d={d} />
            ))}
          </Marquee>
        </section>
      )}

      {indicadores && <FaixaMercado itens={indicadores.itens} />}

      {sinais && <SinaisDeHoje dados={sinais} />}

      <section aria-labelledby="funcionalidades" className="grid gap-10">
        <div className="grid gap-2">
          <h2 id="funcionalidades" className="text-3xl font-semibold tracking-tight">
            O que você encontra aqui
          </h2>
          <p className="max-w-xl text-muted-foreground">Ferramentas para estudar um ativo, comparar com outros e acompanhar o que você já tem.</p>
        </div>
        <div className="grid gap-x-10 gap-y-12 md:grid-cols-3">
          {GRUPOS.map((g) => (
            <div key={g.titulo} className="grid content-start gap-3 border-t-2 border-foreground pt-5">
              <div>
                <h3 className="text-lg font-semibold">{g.titulo}</h3>
                <p className="text-sm text-muted-foreground">{g.descricao}</p>
              </div>
              <div className="grid">
                {g.itens.map((i) => (
                  <LinhaFuncionalidade key={i.titulo} item={i} />
                ))}
              </div>
            </div>
          ))}
        </div>
      </section>

      <section className="grid items-center gap-6 rounded-2xl border border-transparent bg-tinta px-6 py-12 text-[#f3f4f6] sm:px-12 dark:border-border md:grid-cols-[1fr_auto]">
        <div className="grid gap-2">
          <h2 className="text-3xl font-semibold tracking-tight">Crie sua conta grátis</h2>
          <p className="max-w-lg text-[#f3f4f6]/75">Guarde sua carteira, sua watchlist e seus alertas, e acesse de qualquer aparelho.</p>
        </div>
        <div className="flex flex-wrap gap-3">
          <Button asChild size="lg">
            <Link href="/cadastro">Criar conta</Link>
          </Button>
          <Button asChild size="lg" variant="ghost" className="text-[#f3f4f6] hover:bg-white/10 hover:text-white">
            <Link href="/entrar">Já tenho conta</Link>
          </Button>
        </div>
      </section>
    </div>
  );
}
