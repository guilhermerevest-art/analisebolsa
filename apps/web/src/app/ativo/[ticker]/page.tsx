import { Calculator, FlaskConical, GitCompareArrows, Scale } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { notFound, redirect } from "next/navigation";

import { Abas } from "@/components/ativo/abas";
import { PainelAnalise } from "@/components/ativo/analise";
import { CabecalhoAtivo } from "@/components/ativo/cabecalho-ativo";
import { PainelFundamentos } from "@/components/ativo/fundamentos";
import { GraficoCliente } from "@/components/ativo/grafico-cliente";
import { PainelProventos } from "@/components/ativo/proventos";
import { AvisoEducacional } from "@/components/aviso-educacional";
import { Termo } from "@/components/dica";
import { lerAnalise, lerAtivo, lerFundamentos, lerProventos } from "@/lib/dados";
import { formatarPct, formatarPreco, NOMES_TIPO } from "@/lib/formato";

export const revalidate = 3600;

type Props = { params: Promise<{ ticker: string }> };

const REGEX_TICKER = /^[A-Z0-9]{4,6}$/;

async function tickerDaUrl(params: Props["params"]): Promise<string> {
  const { ticker } = await params;
  const normalizado = decodeURIComponent(ticker).toUpperCase();
  if (!REGEX_TICKER.test(normalizado)) notFound();
  if (normalizado !== ticker) redirect(`/ativo/${normalizado}`);
  return normalizado;
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const ticker = await tickerDaUrl(params);
  const ativo = await lerAtivo(ticker);
  if (!ativo) return { title: ticker };
  const preco = ativo.ultima_cotacao ? ` ${formatarPreco(ativo.ultima_cotacao.fechamento)} (${formatarPct(ativo.variacoes.dia)} no dia).` : "";
  const descricao = `${ativo.ticker} (${ativo.nome}), ${NOMES_TIPO[ativo.tipo]} da B3: gráfico, indicadores técnicos, fundamentos e proventos.${preco}`;
  return {
    title: `${ativo.ticker}: cotação, gráfico e fundamentos`,
    description: descricao,
    alternates: { canonical: `/ativo/${ativo.ticker}` },
    openGraph: { title: `${ativo.ticker} · analisebolsa`, description: descricao },
  };
}

export default async function PaginaAtivo({ params }: Props) {
  const ticker = await tickerDaUrl(params);
  const [ativo, fundamentos, proventos, analise] = await Promise.all([
    lerAtivo(ticker),
    lerFundamentos(ticker),
    lerProventos(ticker),
    lerAnalise(ticker),
  ]);
  if (!ativo) notFound();

  return (
    <div className="grid gap-8">
      <CabecalhoAtivo ativo={ativo} />
      <section aria-label="Gráfico">
        <GraficoCliente ticker={ativo.ticker} niveis={analise?.cenario?.niveis} />
        <p className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground">
          <span className="font-medium text-foreground">Entenda o gráfico:</span>
          <Termo termo="candle">Candles</Termo>
          <Termo termo="volume">Volume</Termo>
          <Termo termo="mm">Médias móveis</Termo>
          <Termo termo="bollinger">Bollinger</Termo>
          <Termo termo="rsi">RSI</Termo>
          <Termo termo="macd">MACD</Termo>
          <Link href="/glossario" className="text-azul underline-offset-2 hover:underline">
            Glossário completo
          </Link>
        </p>
      </section>
      <nav aria-label="Ferramentas" className="-mt-4 flex flex-wrap gap-2 text-sm">
        <Link href={`/backtest?ticker=${ativo.ticker}`} className="inline-flex items-center gap-1.5 rounded-md border px-3 py-1.5 hover:bg-muted">
          <FlaskConical className="size-4" aria-hidden />
          Testar uma estratégia
        </Link>
        <Link href={`/simulador?ticker=${ativo.ticker}&inicio=2015-01&inicial=1.000&mensal=500`} className="inline-flex items-center gap-1.5 rounded-md border px-3 py-1.5 hover:bg-muted">
          <Calculator className="size-4" aria-hidden />
          Simular aportes
        </Link>
        <Link href={`/posicao?ticker=${ativo.ticker}&modo=atr`} className="inline-flex items-center gap-1.5 rounded-md border px-3 py-1.5 hover:bg-muted">
          <Scale className="size-4" aria-hidden />
          Calcular posição
        </Link>
        <Link href={`/comparar?t=${ativo.tipo === "acao" ? `${ativo.ticker},BOVA11` : ativo.ticker}`} className="inline-flex items-center gap-1.5 rounded-md border px-3 py-1.5 hover:bg-muted">
          <GitCompareArrows className="size-4" aria-hidden />
          Comparar com outros
        </Link>
      </nav>
      <Abas
        abas={[
          { id: "analise", rotulo: "Análise", conteudo: <PainelAnalise dados={analise} /> },
          { id: "fundamentos", rotulo: "Fundamentos", conteudo: <PainelFundamentos dados={fundamentos} /> },
          { id: "proventos", rotulo: "Proventos", conteudo: <PainelProventos dados={proventos} /> },
          {
            id: "sobre",
            rotulo: "Sobre",
            conteudo: (
              <dl className="grid max-w-lg grid-cols-[auto_1fr] gap-x-6 gap-y-2 text-sm">
                <dt className="text-muted-foreground">Nome</dt>
                <dd>{ativo.nome}</dd>
                <dt className="text-muted-foreground">Tipo</dt>
                <dd>{NOMES_TIPO[ativo.tipo]}</dd>
                <dt className="text-muted-foreground">Setor</dt>
                <dd>{ativo.setor ?? "—"}</dd>
                <dt className="text-muted-foreground">Segmento</dt>
                <dd>{ativo.segmento ?? "—"}</dd>
              </dl>
            ),
          },
        ]}
      />
      <div className="rounded-xl border border-dashed bg-card p-4">
        <AvisoEducacional />
      </div>
    </div>
  );
}
