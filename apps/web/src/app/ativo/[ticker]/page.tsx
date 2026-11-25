import type { Metadata } from "next";
import { notFound, redirect } from "next/navigation";

import { Abas } from "@/components/ativo/abas";
import { PainelAnalise } from "@/components/ativo/analise";
import { CabecalhoAtivo } from "@/components/ativo/cabecalho-ativo";
import { PainelFundamentos } from "@/components/ativo/fundamentos";
import { GraficoCliente } from "@/components/ativo/grafico-cliente";
import { PainelProventos } from "@/components/ativo/proventos";
import { AvisoEducacional } from "@/components/aviso-educacional";
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
      </section>
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
      <div className="rounded-lg border border-dashed p-4">
        <AvisoEducacional />
      </div>
    </div>
  );
}
