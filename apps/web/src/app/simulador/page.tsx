import { Lightbulb } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";

import { Campo } from "@/components/campo";
import { Termo } from "@/components/dica";
import { GraficoLinhasCliente } from "@/components/graficos/grafico-linhas-cliente";
import type { SerieLinha } from "@/components/graficos/grafico-linhas";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { lerSimulacao } from "@/lib/dados";
import { formatarData, formatarPreco } from "@/lib/formato";
import type { ChaveGlossario } from "@/lib/glossario";
import { fimDeCadaAno, INICIO_MINIMO, leituraSimulador, lerParamsSimulador, mesMaximo } from "@/lib/simulador";
import type { Simulacao } from "@/lib/tipos-api";

export const metadata: Metadata = {
  title: "Simulador de aportes",
  description: "Aportes mensais num ativo da B3, com proventos reinvestidos, comparados ao CDI e ao IPCA no mesmo período.",
};

type Props = { searchParams: Promise<Record<string, string | string[] | undefined>> };

// Paleta validada (scripts/validate_palette.js do dataviz) no claro e no escuro; o total
// aportado é a referência, em cinza tracejado.
const SERIES_HISTORICO: SerieLinha[] = [
  { chave: "patrimonio", rotulo: "No ativo", claro: "#1f51ff", escuro: "#5b87ff" },
  { chave: "cdi", rotulo: "No CDI", claro: "#d97706", escuro: "#d97706" },
  { chave: "ipca", rotulo: "Corrigido pelo IPCA", claro: "#9333ea", escuro: "#a855f7" },
  { chave: "aportado", rotulo: "Total aportado", claro: "#6b7180", escuro: "#9aa0ac", tracejada: true },
];
const SERIES_FAIXA: SerieLinha[] = [
  { chave: "p90", rotulo: "Percentil 90", claro: "#1f51ff", escuro: "#5b87ff", tracejada: true },
  { chave: "p50", rotulo: "Mediana", claro: "#1f51ff", escuro: "#5b87ff" },
  { chave: "p10", rotulo: "Percentil 10", claro: "#1f51ff", escuro: "#5b87ff", tracejada: true },
  { chave: "real", rotulo: "Histórico real", claro: "#3a3f4a", escuro: "#c9ccd3" },
];

function Valor({ rotulo, valor, detalhe, termo }: { rotulo: string; valor: string; detalhe?: string; termo?: ChaveGlossario }) {
  return (
    <div className="rounded-xl border bg-card p-4">
      <dt className="text-sm text-muted-foreground">{termo ? <Termo termo={termo}>{rotulo}</Termo> : rotulo}</dt>
      <dd className="mt-1 text-xl font-semibold tabular-nums">{valor}</dd>
      {detalhe && <dd className="text-xs text-muted-foreground">{detalhe}</dd>}
    </div>
  );
}

const mesAno = (iso: string | null | undefined) => (iso ? iso.slice(0, 7).split("-").reverse().join("/") : "—");

export default async function PaginaSimulador({ searchParams }: Props) {
  const { entrada, erros, consulta } = lerParamsSimulador(await searchParams);
  const sim = consulta ? await lerSimulacao(consulta) : null;
  const tickerInexistente = consulta !== null && sim === null;
  const valoresIniciais = consulta ? entrada : { ...entrada, inicio: "2015-01", inicial: "1.000", mensal: "500" };

  return (
    <div className="grid grid-cols-[minmax(0,1fr)] gap-8">
      <div>
        <h1 className="text-3xl font-semibold tracking-tight">Simulador de aportes</h1>
        <p className="mt-1 max-w-2xl text-muted-foreground">
          Veja como teriam evoluído aportes mensais num ativo, com os proventos reinvestidos, e os mesmos aportes no CDI e corrigidos pelo
          IPCA. Sem ativo, a comparação fica só entre CDI e IPCA.
        </p>
      </div>

      <form method="get" action="/simulador" className="grid gap-4 rounded-xl border bg-card p-4 sm:grid-cols-2 lg:grid-cols-[1fr_1fr_1fr_1fr_auto]">
        <Campo
          nome="ticker"
          rotulo="Ativo (opcional)"
          placeholder="PETR4"
          defaultValue={valoresIniciais.ticker}
          autoCapitalize="characters"
          autoComplete="off"
          maxLength={6}
          erro={erros.ticker ?? (tickerInexistente ? "Ativo não encontrado" : undefined)}
        />
        <Campo nome="inicio" rotulo="Início" type="month" min={INICIO_MINIMO} max={mesMaximo()} defaultValue={valoresIniciais.inicio} required erro={erros.inicio} />
        <Campo nome="inicial" rotulo="Aporte inicial (R$)" inputMode="decimal" placeholder="0" defaultValue={valoresIniciais.inicial} erro={erros.inicial ?? erros.aportes} />
        <Campo nome="mensal" rotulo="Aporte mensal (R$)" inputMode="decimal" placeholder="0" defaultValue={valoresIniciais.mensal} erro={erros.mensal} />
        <div className="grid content-start gap-3 sm:col-span-2 lg:col-span-1">
          <div className="flex h-[14px] items-center gap-2">
            <input type="hidden" name="reinvestir" value="0" />
            <input id="reinvestir" type="checkbox" name="reinvestir" value="1" defaultChecked={valoresIniciais.reinvestir} className="size-4 accent-[var(--azul)]" />
            <Label htmlFor="reinvestir" className="font-normal">
              Reinvestir proventos
            </Label>
          </div>
          <Button type="submit">Simular</Button>
        </div>
      </form>

      {sim && sim.pontos.length === 0 && <p className="text-sm text-muted-foreground">Não há dados para esse período.</p>}
      {sim && sim.pontos.length > 0 && <Resultado sim={sim} />}

      {!consulta && (
        <p className="text-sm text-muted-foreground">
          O aporte mensal entra no primeiro pregão de cada mês, inclusive no primeiro mês, ao preço de fechamento. Quer acompanhar uma carteira
          real? Use a <Link href="/carteira" className="underline">Carteira</Link>.
        </p>
      )}
    </div>
  );
}

function Resultado({ sim }: { sim: Simulacao }) {
  const final = sim.pontos.at(-1)!;
  const comAtivo = sim.ticker !== null;
  const anos = fimDeCadaAno(sim.pontos).reverse();
  const real = new Map(sim.pontos.map((p) => [p.data, p.patrimonio]));
  const faixaFinal = sim.faixa?.pontos.at(-1);

  return (
    <>
      <section aria-labelledby="titulo-resultado" className="grid gap-4">
        <h2 id="titulo-resultado" className="text-xl font-semibold">
          {comAtivo ? sim.ticker : "CDI e IPCA"} de {mesAno(sim.inicio)} a {mesAno(sim.fim)}
        </h2>
        <dl className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <Valor rotulo="Total aportado" valor={formatarPreco(final.aportado)} />
          {comAtivo && (
            <Valor rotulo={`No ativo (${sim.ticker})`} termo="proventos" valor={formatarPreco(final.patrimonio)} detalhe={`${formatarPreco(final.proventos)} em proventos`} />
          )}
          <Valor rotulo="No CDI" termo="cdi" valor={formatarPreco(final.cdi)} />
          <Valor rotulo="Corrigido pelo IPCA" termo="ipca" valor={formatarPreco(final.ipca)} detalhe={sim.ipca_ate ? `IPCA até ${mesAno(sim.ipca_ate)}` : undefined} />
        </dl>
        <aside aria-labelledby="titulo-leitura" className="grid gap-2 rounded-xl border-l-4 border-l-azul bg-accent/60 p-4 text-sm leading-relaxed">
          <h3 id="titulo-leitura" className="flex items-center gap-2 font-semibold">
            <Lightbulb aria-hidden className="size-4 text-azul" />
            Como ler este resultado
          </h3>
          {leituraSimulador({
            aportado: Number(final.aportado),
            ativo: comAtivo ? Number(final.patrimonio) : null,
            ticker: sim.ticker,
            cdi: Number(final.cdi),
            ipca: Number(final.ipca),
          }).map((f) => (
            <p key={f}>{f}</p>
          ))}
        </aside>
        <GraficoLinhasCliente
          pontos={sim.pontos}
          series={SERIES_HISTORICO}
          formato="brl"
          rotuloAcessivel="Evolução do patrimônio no ativo, no CDI, corrigido pelo IPCA e do total aportado, mês a mês"
        />
        <div className="relative overflow-x-auto">
          <table className="w-full text-sm">
            <caption className="sr-only">Valores no fim de cada ano</caption>
            <thead className="text-muted-foreground">
              <tr>
                <th scope="col" className="py-2 text-left font-normal">Fim de</th>
                <th scope="col" className="py-2 pl-3 text-right font-normal">Aportado</th>
                {comAtivo && <th scope="col" className="py-2 pl-3 text-right font-normal">No ativo</th>}
                {comAtivo && <th scope="col" className="py-2 pl-3 text-right font-normal">Proventos</th>}
                <th scope="col" className="py-2 pl-3 text-right font-normal">No CDI</th>
                <th scope="col" className="py-2 pl-3 text-right font-normal">IPCA</th>
              </tr>
            </thead>
            <tbody>
              {anos.map((p) => (
                <tr key={p.data} className="border-t">
                  <td className="py-1.5 tabular-nums">{p === final ? formatarData(p.data) : p.data.slice(0, 4)}</td>
                  <td className="py-1.5 pl-3 text-right tabular-nums">{formatarPreco(p.aportado)}</td>
                  {comAtivo && <td className="py-1.5 pl-3 text-right tabular-nums">{formatarPreco(p.patrimonio)}</td>}
                  {comAtivo && <td className="py-1.5 pl-3 text-right tabular-nums">{formatarPreco(p.proventos)}</td>}
                  <td className="py-1.5 pl-3 text-right tabular-nums">{formatarPreco(p.cdi)}</td>
                  <td className="py-1.5 pl-3 text-right tabular-nums">{formatarPreco(p.ipca)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {comAtivo && (
        <section aria-labelledby="titulo-faixa" className="grid gap-4">
          <h2 id="titulo-faixa" className="text-xl font-semibold">
            <Termo termo="simulacao">Faixa de resultados simulados</Termo>
          </h2>
          {sim.faixa && faixaFinal ? (
            <>
              <p className="max-w-3xl text-sm text-muted-foreground">{sim.faixa.explicacao}</p>
              <dl className="grid gap-3 sm:grid-cols-3">
                <Valor rotulo="Percentil 10" valor={formatarPreco(faixaFinal.p10)} />
                <Valor rotulo="Mediana" valor={formatarPreco(faixaFinal.p50)} />
                <Valor rotulo="Percentil 90" valor={formatarPreco(faixaFinal.p90)} />
              </dl>
              <GraficoLinhasCliente
                pontos={sim.faixa.pontos.map((p) => ({ ...p, real: real.get(p.data) ?? null }))}
                series={SERIES_FAIXA}
                formato="brl"
                rotuloAcessivel="Percentis 10, 50 e 90 do patrimônio nas trajetórias simuladas, com o histórico real"
              />
              <p className="text-xs text-muted-foreground">
                Baseada em {sim.faixa.meses_historico} meses de retornos de {sim.ticker}.
              </p>
            </>
          ) : (
            <p className="text-sm text-muted-foreground">A faixa aparece para ativos com pelo menos 5 anos de histórico de cotações.</p>
          )}
        </section>
      )}

      <p className="text-xs text-muted-foreground">{sim.aviso}</p>
    </>
  );
}
