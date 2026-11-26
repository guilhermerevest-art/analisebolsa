import { Lightbulb } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";

import { FormularioBacktest } from "@/components/backtest/formulario-backtest";
import { Termo } from "@/components/dica";
import { GraficoOperacoesCliente } from "@/components/backtest/grafico-operacoes-cliente";
import { GraficoLinhasCliente } from "@/components/graficos/grafico-linhas-cliente";
import type { SerieLinha } from "@/components/graficos/grafico-linhas";
import { leituraBacktest, lerParamsBacktest, mesAtual } from "@/lib/backtest";
import { lerBacktest } from "@/lib/dados";
import { classeVariacao, formatarData, formatarPct, formatarPreco } from "@/lib/formato";
import type { Backtest, MetricasBacktest } from "@/lib/tipos-api";
import type { ChaveGlossario } from "@/lib/glossario";
import { cn } from "@/lib/utils";

export const metadata: Metadata = {
  title: "Backtest de estratégias",
  description: "Teste regras conhecidas de análise técnica no histórico de um ativo da B3, com custos, comparadas a manter o ativo e ao CDI.",
};

type Props = { searchParams: Promise<Record<string, string | string[] | undefined>> };

// Mesma paleta validada do simulador: estratégia em azul, manter o ativo em roxo, CDI em âmbar.
const SERIES_PATRIMONIO: SerieLinha[] = [
  { chave: "estrategia", rotulo: "Estratégia", claro: "#1f51ff", escuro: "#5b87ff" },
  { chave: "buy_and_hold", rotulo: "Manter o ativo", claro: "#9333ea", escuro: "#a855f7" },
  { chave: "cdi", rotulo: "CDI", claro: "#d97706", escuro: "#d97706" },
];
const SERIES_DRAWDOWN: SerieLinha[] = [
  { chave: "drawdown", rotulo: "Estratégia", claro: "#1f51ff", escuro: "#5b87ff" },
  { chave: "drawdown_bh", rotulo: "Manter o ativo", claro: "#9333ea", escuro: "#a855f7" },
];

const pct = (v: number | null | undefined) => (v === null || v === undefined ? "—" : formatarPct(v * 100));
const pctSemSinal = (v: number | null | undefined, casas = 1) =>
  v === null || v === undefined ? "—" : `${(v * 100).toLocaleString("pt-BR", { maximumFractionDigits: casas })}%`;
const numero = (v: number | null | undefined) => (v === null || v === undefined ? "—" : v.toLocaleString("pt-BR", { maximumFractionDigits: 2 }));
const maiuscula = (t: string) => t.charAt(0).toUpperCase() + t.slice(1);

export default async function PaginaBacktest({ searchParams }: Props) {
  const { entrada, erros, consulta } = lerParamsBacktest(await searchParams);
  const resposta = consulta ? await lerBacktest(consulta) : null;
  const erroApi = resposta && "erro" in resposta ? resposta : null;
  const dados = resposta && "dados" in resposta ? resposta.dados : null;

  return (
    <div className="grid grid-cols-[minmax(0,1fr)] gap-8">
      <div>
        <h1 className="text-3xl font-semibold tracking-tight">Backtest de estratégias</h1>
        <p className="mt-1 max-w-2xl text-muted-foreground">
          Veja como uma regra de análise técnica teria se comportado no histórico de um ativo, com custos, ao lado de manter o ativo o tempo todo e
          do CDI. É um exercício sobre o passado para entender a regra, não um sinal para hoje.
        </p>
      </div>

      <FormularioBacktest
        key={consulta?.toString() ?? "vazio"}
        inicial={entrada}
        erros={erros}
        erroTicker={erroApi?.status === 404 ? "Ativo não encontrado" : undefined}
        mesMaximo={mesAtual()}
      />

      {erroApi?.status === 422 && <p className="text-sm text-destructive">{maiuscula(erroApi.erro)}.</p>}
      {dados && <Resultado r={dados} />}
      <Vieses />
    </div>
  );
}

function Resultado({ r }: { r: Backtest }) {
  const t = r.total;
  return (
    <>
      <section aria-labelledby="titulo-resultado" className="grid gap-4">
        <div>
          <h2 id="titulo-resultado" className="text-xl font-semibold">
            {r.nome} em {r.ticker}, de {formatarData(r.inicio)} a {formatarData(r.fim)}
          </h2>
          <p className="mt-1 text-sm text-muted-foreground">
            {r.regra}
            {r.stop_atr ? ` Stop a ${numero(r.stop_atr)} ATR abaixo da entrada.` : ""}
          </p>
        </div>
        <dl className="grid gap-3 sm:grid-cols-3">
          <Valor rotulo="Estratégia" termo="backtest" valor={pct(t.estrategia.retorno_total)} detalhe={`${pct(t.estrategia.retorno_anual)} ao ano`} cor={t.estrategia.retorno_total} />
          <Valor rotulo="Manter o ativo" termo="buy_and_hold" valor={pct(t.buy_and_hold.retorno_total)} detalhe={`${pct(t.buy_and_hold.retorno_anual)} ao ano`} cor={t.buy_and_hold.retorno_total} />
          <Valor rotulo="CDI" termo="cdi" valor={pct(t.cdi.retorno_total)} detalhe={`${pct(t.cdi.retorno_anual)} ao ano`} cor={t.cdi.retorno_total} />
        </dl>
        <LeituraResultado r={r} />
        <h3 className="text-sm font-medium">Entradas e saídas no preço</h3>
        <p className="-mt-2 text-sm text-muted-foreground">{estadoDaRegra(r)}</p>
        <GraficoOperacoesCliente pontos={r.pontos} operacoes={r.operacoes} />
        <h3 className="text-sm font-medium">Patrimônio (base 100)</h3>
        <GraficoLinhasCliente
          pontos={r.pontos}
          series={SERIES_PATRIMONIO}
          formato="num"
          rotuloAcessivel="Evolução do patrimônio da estratégia, de manter o ativo e do CDI, com base 100 no início"
        />
        <h3 className="text-sm font-medium">Queda desde o topo</h3>
        <GraficoLinhasCliente
          pontos={r.pontos}
          series={SERIES_DRAWDOWN}
          formato="pct"
          altura="h-44"
          rotuloAcessivel="Queda percentual desde o maior valor anterior, da estratégia e de manter o ativo"
        />
      </section>

      <section aria-labelledby="titulo-metricas" className="grid gap-3">
        <h2 id="titulo-metricas" className="text-xl font-semibold">
          Métricas do período
        </h2>
        <TabelaMetricas c={r.total} />
        <p className="text-xs text-muted-foreground">
          Capital de {formatarPreco(r.capital)}. Custos de {formatarPreco(r.custos.corretagem)} por ordem, {pctSemSinal(r.custos.taxas, 3)} de taxas e{" "}
          {pctSemSinal(r.custos.deslizamento, 3)} de deslizamento em cada execução, somando {formatarPreco(r.custos.total)} na estratégia.
          {r.cdi_no_caixa ? " Fora da posição, o caixa rende o CDI." : " Fora da posição, o caixa fica parado."}
        </p>
      </section>

      <section aria-labelledby="titulo-amostra" className="grid gap-3">
        <h2 id="titulo-amostra" className="text-xl font-semibold">
          <Termo termo="dentro_fora_amostra">Dentro e fora da amostra</Termo>
        </h2>
        <p className="max-w-3xl text-sm text-muted-foreground">
          O período foi dividido em dois: os primeiros 70% (até {formatarData(r.divisao)}) e os últimos 30%. Uma regra que só funciona num dos trechos
          provavelmente depende de um momento específico do mercado. Se você ajustou os parâmetros olhando o resultado, o trecho final deixa de ser
          um teste independente.
        </p>
        <div className="relative overflow-x-auto">
          <table className="w-full text-sm">
            <caption className="sr-only">Métricas antes e depois da divisão</caption>
            <thead className="text-muted-foreground">
              <tr>
                <th scope="col" className="py-2 text-left font-normal">Trecho</th>
                <th scope="col" className="py-2 pl-3 text-right font-normal">Estratégia</th>
                <th scope="col" className="py-2 pl-3 text-right font-normal">Manter o ativo</th>
                <th scope="col" className="py-2 pl-3 text-right font-normal">CDI</th>
                <th scope="col" className="py-2 pl-3 text-right font-normal">Queda máxima</th>
                <th scope="col" className="py-2 pl-3 text-right font-normal">Operações</th>
              </tr>
            </thead>
            <tbody>
              {[
                { nome: `Dentro (até ${formatarData(r.divisao)})`, c: r.dentro_amostra },
                { nome: `Fora (de ${formatarData(r.divisao)})`, c: r.fora_amostra },
              ].map(({ nome, c }) => (
                <tr key={nome} className="border-t">
                  <th scope="row" className="py-1.5 text-left font-normal">{nome}</th>
                  <Celula v={c.estrategia.retorno_total} cor />
                  <Celula v={c.buy_and_hold.retorno_total} cor />
                  <Celula v={c.cdi.retorno_total} cor />
                  <Celula v={c.estrategia.drawdown_maximo} />
                  <td className="py-1.5 pl-3 text-right tabular-nums">{c.estrategia.operacoes ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <Operacoes r={r} />
      <p className="text-xs text-muted-foreground">{r.aviso}</p>
    </>
  );
}

function estadoDaRegra(r: Backtest): string {
  const ultima = r.operacoes.at(-1);
  if (!ultima) return "A regra não gerou nenhuma entrada no período.";
  if (ultima.motivo === "aberta") {
    return `No último pregão (${formatarData(r.fim)}), pela regra a posição estava aberta desde ${formatarData(ultima.entrada)}, com ${pct(ultima.resultado)} até ali.`;
  }
  return `No último pregão (${formatarData(r.fim)}), pela regra a posição estava fora desde ${formatarData(ultima.saida!)}${ultima.motivo === "stop" ? ", quando o stop foi atingido" : ""}.`;
}

function LeituraResultado({ r }: { r: Backtest }) {
  const t = r.total;
  const frases = leituraBacktest({
    capital: Number(r.capital),
    estrategia: { retorno: t.estrategia.retorno_total ?? null, queda: t.estrategia.drawdown_maximo ?? null },
    manter: { retorno: t.buy_and_hold.retorno_total ?? null, queda: t.buy_and_hold.drawdown_maximo ?? null },
    cdi: { retorno: t.cdi.retorno_total ?? null },
  });
  if (frases.length === 0) return null;
  return (
    <aside aria-labelledby="titulo-leitura" className="grid gap-2 rounded-xl border-l-4 border-l-azul bg-accent/60 p-4 text-sm leading-relaxed">
      <h3 id="titulo-leitura" className="flex items-center gap-2 font-semibold">
        <Lightbulb aria-hidden className="size-4 text-azul" />
        Como ler este resultado
      </h3>
      {frases.map((f) => (
        <p key={f}>{f}</p>
      ))}
    </aside>
  );
}

function Valor({ rotulo, termo, valor, detalhe, cor }: { rotulo: string; termo: ChaveGlossario; valor: string; detalhe: string; cor: number }) {
  return (
    <div className="rounded-xl border bg-card p-4">
      <dt className="text-sm text-muted-foreground">
        <Termo termo={termo}>{rotulo}</Termo>
      </dt>
      <dd className={cn("mt-1 text-xl font-semibold tabular-nums", classeVariacao(cor))}>{valor}</dd>
      <dd className="text-xs text-muted-foreground">{detalhe}</dd>
    </div>
  );
}

function Celula({ v, cor }: { v: number | null | undefined; cor?: boolean }) {
  return <td className={cn("py-1.5 pl-3 text-right tabular-nums", cor && classeVariacao(v ?? null))}>{pct(v)}</td>;
}

const LINHAS: { rotulo: string; ajuda: string; termo?: ChaveGlossario; valor: (m: MetricasBacktest) => string }[] = [
  { rotulo: "Retorno total", ajuda: "", termo: "retorno_total", valor: (m) => pct(m.retorno_total) },
  { rotulo: "Retorno ao ano", ajuda: "composto", termo: "retorno_anual", valor: (m) => pct(m.retorno_anual) },
  { rotulo: "Volatilidade ao ano", ajuda: "oscilação diária anualizada", termo: "volatilidade", valor: (m) => pctSemSinal(m.volatilidade) },
  { rotulo: "Queda máxima", ajuda: "maior queda desde um topo", termo: "queda_maxima", valor: (m) => pct(m.drawdown_maximo) },
  { rotulo: "Índice de Sharpe", ajuda: "retorno acima do CDI por unidade de oscilação", termo: "sharpe", valor: (m) => numero(m.sharpe) },
  { rotulo: "Tempo posicionado", ajuda: "", termo: "tempo_posicionado", valor: (m) => pctSemSinal(m.exposicao) },
  { rotulo: "Operações", ajuda: "", valor: (m) => (m.operacoes === null || m.operacoes === undefined ? "—" : String(m.operacoes)) },
  { rotulo: "Operações positivas", ajuda: "das encerradas", termo: "operacoes_positivas", valor: (m) => pctSemSinal(m.acertos) },
  { rotulo: "Resultado médio", ajuda: "por operação encerrada, com custos", valor: (m) => pct(m.resultado_medio) },
];

function TabelaMetricas({ c }: { c: Backtest["total"] }) {
  return (
    <div className="relative overflow-x-auto">
      <table className="w-full text-sm">
        <caption className="sr-only">Métricas da estratégia, de manter o ativo e do CDI</caption>
        <thead className="text-muted-foreground">
          <tr>
            <th scope="col" className="py-2 text-left font-normal">Métrica</th>
            <th scope="col" className="py-2 pl-3 text-right font-normal">Estratégia</th>
            <th scope="col" className="py-2 pl-3 text-right font-normal">Manter o ativo</th>
            <th scope="col" className="py-2 pl-3 text-right font-normal">CDI</th>
          </tr>
        </thead>
        <tbody>
          {LINHAS.map((l) => (
            <tr key={l.rotulo} className="border-t">
              <th scope="row" className="py-1.5 text-left font-normal">
                {l.termo ? <Termo termo={l.termo}>{l.rotulo}</Termo> : l.rotulo}
                {l.ajuda && <span className="block text-xs text-muted-foreground">{l.ajuda}</span>}
              </th>
              <td className="py-1.5 pl-3 text-right tabular-nums">{l.valor(c.estrategia)}</td>
              <td className="py-1.5 pl-3 text-right tabular-nums">{l.valor(c.buy_and_hold)}</td>
              <td className="py-1.5 pl-3 text-right tabular-nums">{l.valor(c.cdi)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

const MOTIVOS = { sinal: "Regra", stop: "Stop", aberta: "Em aberto" } as const;
const LIMITE_OPERACOES = 100;

function Operacoes({ r }: { r: Backtest }) {
  if (r.operacoes.length === 0) {
    return <p className="text-sm text-muted-foreground">A regra não gerou nenhuma entrada nesse período.</p>;
  }
  const lista = r.operacoes.slice(-LIMITE_OPERACOES).reverse();
  return (
    <section aria-labelledby="titulo-operacoes" className="grid gap-3">
      <h2 id="titulo-operacoes" className="text-xl font-semibold">
        Operações
      </h2>
      <div className="relative max-h-[28rem] overflow-auto">
        <table className="w-full text-sm">
          <caption className="sr-only">Entradas e saídas da estratégia, da mais recente para a mais antiga</caption>
          <thead className="sticky top-0 bg-background text-muted-foreground">
            <tr>
              <th scope="col" className="py-2 text-left font-normal">Entrada</th>
              <th scope="col" className="py-2 pl-3 text-left font-normal">Saída</th>
              <th scope="col" className="py-2 pl-3 text-right font-normal">Pregões</th>
              <th scope="col" className="py-2 pl-3 text-left font-normal">Motivo</th>
              <th scope="col" className="py-2 pl-3 text-right font-normal">Resultado</th>
            </tr>
          </thead>
          <tbody>
            {lista.map((o) => (
              <tr key={o.entrada} className="border-t">
                <td className="py-1.5 tabular-nums">{formatarData(o.entrada)}</td>
                <td className="py-1.5 pl-3 tabular-nums">{o.saida ? formatarData(o.saida) : "—"}</td>
                <td className="py-1.5 pl-3 text-right tabular-nums">{o.pregoes}</td>
                <td className="py-1.5 pl-3">{MOTIVOS[o.motivo]}</td>
                <td className={cn("py-1.5 pl-3 text-right tabular-nums", classeVariacao(o.resultado))}>{pct(o.resultado)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-xs text-muted-foreground">
        {r.operacoes.length > LIMITE_OPERACOES ? `As ${LIMITE_OPERACOES} mais recentes de ${r.operacoes.length}. ` : ""}
        Preços ajustados por proventos; o resultado já desconta os custos. A posição em aberto é marcada no último fechamento.
      </p>
    </section>
  );
}

function Vieses() {
  return (
    <section aria-labelledby="titulo-vieses" className="grid gap-3 rounded-xl border bg-card p-4">
      <h2 id="titulo-vieses" className="text-lg font-semibold">
        Como o teste é feito e o que ele não mostra
      </h2>
      <ul className="grid gap-2 text-sm text-muted-foreground">
        <li>
          <strong className="font-medium text-foreground">Sem olhar o futuro.</strong> A regra é avaliada no fechamento de cada pregão e a ordem é
          executada na abertura do pregão seguinte. Os indicadores usam só dados até aquele dia.
        </li>
        <li>
          <strong className="font-medium text-foreground">Custos incluídos.</strong> Corretagem, taxas e deslizamento entram em toda entrada e saída.
          Impostos ficam de fora.
        </li>
        <li>
          <strong className="font-medium text-foreground">Viés de sobrevivência.</strong> O catálogo tem só os ativos listados hoje. Empresas que
          saíram da bolsa não aparecem, o que tende a deixar os resultados mais bonitos do que foram.
        </li>
        <li>
          <strong className="font-medium text-foreground">Sobreajuste.</strong> Testar muitos parâmetros até achar um resultado bom quase sempre
          encontra algo que funcionou por acaso. Compare os trechos dentro e fora da amostra.
        </li>
        <li>
          <strong className="font-medium text-foreground">Simplificações.</strong> Posição só comprada, com todo o capital, em quantidade
          fracionária (sem lotes de 100) e proventos reinvestidos pelo preço ajustado.
        </li>
      </ul>
      <p className="text-xs text-muted-foreground">
        Quer ver aportes mensais num ativo em vez de uma regra? Use o <Link href="/simulador" className="underline">Simulador</Link>.
      </p>
    </section>
  );
}
