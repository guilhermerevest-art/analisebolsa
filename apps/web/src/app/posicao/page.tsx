import type { Metadata } from "next";
import Link from "next/link";

import { Campo } from "@/components/campo";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { lerPosicao } from "@/lib/dados";
import { formatarData, formatarPreco } from "@/lib/formato";
import { lerParamsPosicao } from "@/lib/posicao";
import type { Posicao } from "@/lib/tipos-api";
import { classeSelect } from "@/components/ui/select-nativo";

export const metadata: Metadata = {
  title: "Calculadora de posição",
  description: "Quantas ações cabem numa operação para que a perda até o stop fique dentro do risco escolhido.",
};

type Props = { searchParams: Promise<Record<string, string | string[] | undefined>> };

const pct = (v: number, casas = 2) => `${(v * 100).toLocaleString("pt-BR", { maximumFractionDigits: casas })}%`;
const inteiro = (v: number) => v.toLocaleString("pt-BR");
const maiuscula = (t: string) => t.charAt(0).toUpperCase() + t.slice(1);

export default async function PaginaPosicao({ searchParams }: Props) {
  const { entrada, erros, consulta } = lerParamsPosicao(await searchParams);
  const resposta = consulta ? await lerPosicao(consulta) : null;
  const erroApi = resposta && "erro" in resposta ? resposta : null;
  const dados = resposta && "dados" in resposta ? resposta.dados : null;

  return (
    <div className="grid grid-cols-[minmax(0,1fr)] gap-8">
      <div>
        <h1 className="text-3xl font-semibold tracking-tight">Calculadora de posição</h1>
        <p className="mt-1 max-w-2xl text-muted-foreground">
          Defina quanto do capital aceita perder se o stop for atingido. A calculadora mostra a quantidade que mantém essa perda no limite, sem
          passar da fatia máxima do capital numa posição só.
        </p>
      </div>

      <form method="get" action="/posicao" className="grid gap-5 rounded-xl border bg-card p-4">
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Campo nome="capital" rotulo="Capital (R$)" inputMode="decimal" placeholder="50.000" defaultValue={entrada.capital} required erro={erros.capital} />
          <Campo nome="risco" rotulo="Risco por operação (% do capital)" inputMode="decimal" defaultValue={entrada.risco} erro={erros.risco} />
          <Campo
            nome="ticker"
            rotulo="Ativo (opcional)"
            placeholder="PETR4"
            defaultValue={entrada.ticker}
            autoCapitalize="characters"
            autoComplete="off"
            maxLength={6}
            erro={erros.ticker ?? (erroApi?.status === 404 ? "Ativo não encontrado" : undefined)}
          />
          <Campo
            nome="entrada"
            rotulo="Preço de entrada (R$)"
            inputMode="decimal"
            placeholder={entrada.ticker ? "Último fechamento" : "30,00"}
            defaultValue={entrada.entrada}
            erro={erros.entrada}
          />
        </div>

        <fieldset className="grid gap-3">
          <legend className="mb-2 text-sm font-medium">Stop</legend>
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="grid content-start gap-2">
              <label className="flex items-center gap-2 text-sm">
                <input type="radio" name="modo" value="preco" defaultChecked={entrada.modo === "preco"} className="size-4 accent-[var(--cobalto)]" />
                Preço do stop
              </label>
              <Campo nome="stop" rotulo="Stop (R$)" inputMode="decimal" placeholder="27,50" defaultValue={entrada.stop} erro={erros.stop} />
            </div>
            <div className="grid content-start gap-2">
              <label className="flex items-center gap-2 text-sm">
                <input type="radio" name="modo" value="atr" defaultChecked={entrada.modo === "atr"} className="size-4 accent-[var(--cobalto)]" />
                Distância em ATR do ativo
              </label>
              <Campo nome="atr" rotulo="Múltiplo do ATR de 14 pregões" inputMode="decimal" defaultValue={entrada.atr} erro={erros.atr} />
            </div>
          </div>
        </fieldset>

        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <div className="grid content-start gap-2">
            <Label htmlFor="lote">Lote</Label>
            <select id="lote" name="lote" defaultValue={entrada.lote} className={classeSelect}>
              <option value="100">Lote padrão (100)</option>
              <option value="1">Fracionário (1)</option>
            </select>
          </div>
          <Campo nome="concentracao" rotulo="Máximo numa posição (% do capital)" inputMode="decimal" defaultValue={entrada.concentracao} erro={erros.concentracao} />
        </div>
        <div>
          <Button type="submit">Calcular</Button>
        </div>
      </form>

      {erroApi?.status === 422 && <p className="text-sm text-destructive">{maiuscula(erroApi.erro)}.</p>}
      {dados && <Resultado p={dados} />}
      <Explicacao />
    </div>
  );
}

function Valor({ rotulo, valor, detalhe }: { rotulo: string; valor: string; detalhe?: string }) {
  return (
    <div className="rounded-xl border bg-card p-4">
      <dt className="text-sm text-muted-foreground">{rotulo}</dt>
      <dd className="mt-1 text-xl font-semibold tabular-nums">{valor}</dd>
      {detalhe && <dd className="text-xs text-muted-foreground">{detalhe}</dd>}
    </div>
  );
}

function Resultado({ p }: { p: Posicao }) {
  const lote = p.lote === 100 ? "lote padrão" : "fracionário";
  return (
    <section aria-labelledby="titulo-resultado" className="grid gap-4">
      <h2 id="titulo-resultado" className="text-xl font-semibold">
        {p.ativo ? `${p.ativo.ticker}: ` : ""}entrada a {formatarPreco(p.entrada)} e stop a {formatarPreco(p.stop)}
      </h2>
      {p.ativo && (
        <p className="-mt-2 text-sm text-muted-foreground">
          Último fechamento de {formatarPreco(p.ativo.fechamento)} em {formatarData(p.ativo.data)}
          {p.ativo.atr14 !== null ? `, ATR de 14 pregões de ${formatarPreco(p.ativo.atr14)}` : ""}.
        </p>
      )}
      <dl className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Valor rotulo="Quantidade" valor={inteiro(p.quantidade)} detalhe={lote} />
        <Valor rotulo="Valor da posição" valor={formatarPreco(p.valor)} detalhe={`${pct(p.pct_capital, 1)} do capital`} />
        <Valor rotulo="Perda até o stop" valor={formatarPreco(p.perda_stop)} detalhe={`${pct(p.perda_pct_capital)} do capital`} />
        <Valor rotulo="Distância do stop" valor={pct(p.distancia_stop)} detalhe={`${formatarPreco(p.entrada - p.stop)} por ação`} />
      </dl>
      {p.quantidade === 0 && (
        <p className="text-sm text-muted-foreground">
          Com esse capital e esse risco não cabe nem um lote. Experimente o lote fracionário ou um stop mais próximo.
        </p>
      )}
      {p.limitada_por && p.quantidade > 0 && (
        <p className="text-sm text-muted-foreground">
          {p.limitada_por === "concentracao"
            ? `O limite de ${inteiro(p.concentracao)}% do capital numa posição reduziu a quantidade.`
            : "O capital disponível limitou a quantidade."}{" "}
          Pelo risco, a perda poderia chegar a {formatarPreco(p.risco_maximo)}.
        </p>
      )}
      <div className="relative overflow-x-auto">
        <table className="w-full max-w-lg text-sm">
          <caption className="mb-2 text-left text-sm font-medium">Referências de preço em múltiplos da distância até o stop (R)</caption>
          <thead className="text-muted-foreground">
            <tr>
              <th scope="col" className="py-2 text-left font-normal">Múltiplo</th>
              <th scope="col" className="py-2 pl-3 text-right font-normal">Preço</th>
              <th scope="col" className="py-2 pl-3 text-right font-normal">Variação no valor da posição</th>
            </tr>
          </thead>
          <tbody>
            {p.alvos.map((a) => (
              <tr key={a.multiplo} className="border-t">
                <td className="py-1.5">{a.multiplo}R</td>
                <td className="py-1.5 pl-3 text-right tabular-nums">{formatarPreco(a.preco)}</td>
                <td className="py-1.5 pl-3 text-right tabular-nums">{formatarPreco(p.quantidade * (a.preco - p.entrada))}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-xs text-muted-foreground">{p.aviso}</p>
    </section>
  );
}

function Explicacao() {
  return (
    <section aria-labelledby="titulo-conta" className="grid gap-2 rounded-xl border bg-card p-4 text-sm text-muted-foreground">
      <h2 id="titulo-conta" className="text-lg font-semibold text-foreground">
        Como a conta é feita
      </h2>
      <p>
        Quantidade = (capital × risco%) ÷ (entrada − stop), arredondada para baixo no lote. Com R$ 50.000, risco de 1% (R$ 500) e stop R$ 2 abaixo
        da entrada, cabem 250 ações; no lote padrão, 200.
      </p>
      <p>
        O ATR (amplitude média de 14 pregões) mede quanto o ativo costuma oscilar por dia. Um stop a 2 ATR fica fora da oscilação comum, e ativos
        mais voláteis recebem posições menores para o mesmo risco.
      </p>
      <p>
        R é a distância entre a entrada e o stop. Os preços em 1R, 2R e 3R mostram quanto o ativo precisaria andar para o ganho igualar uma, duas
        ou três vezes a perda até o stop. Quer ver uma regra completa no histórico? Use o <Link href="/backtest" className="underline">Backtest</Link>.
      </p>
    </section>
  );
}
