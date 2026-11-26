"use client";

import Link from "next/link";
import { useActionState, useEffect, useRef, useState } from "react";

import { Campo } from "@/components/campo";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { classeSelect } from "@/components/ui/select-nativo";
import { type EstadoInvestimento, salvarInvestimento } from "@/lib/acoes-carteira";
import type { InvestimentoCarteira } from "@/lib/tipos-api";

const TIPOS = [
  ["cdb", "CDB"],
  ["lci_lca", "LCI/LCA"],
  ["tesouro", "Tesouro Direto"],
  ["debenture", "Debênture"],
  ["outro_rf", "Outro de renda fixa"],
  ["fundo", "Fundo de investimento"],
] as const;

const INDEXADORES = [
  ["cdi", "Pós-fixado (% do CDI)", "Taxa (% do CDI)", "110"],
  ["prefixado", "Prefixado", "Taxa (% ao ano)", "12,5"],
  ["ipca", "IPCA +", "Taxa além do IPCA (% ao ano)", "6"],
] as const;

const br = (v: number | null | undefined) => (v === null || v === undefined ? undefined : String(v).replace(".", ","));

type Props = { carteira: number; hoje: string; investimento?: InvestimentoCarteira };

export function FormularioInvestimento({ carteira, hoje, investimento: inv }: Props) {
  const [estado, acao, pendente] = useActionState<EstadoInvestimento, FormData>(salvarInvestimento, {});
  const [tipo, setTipo] = useState<string>(inv?.tipo ?? "cdb");
  const [indexador, setIndexador] = useState<string>(inv?.indexador ?? "cdi");
  const [resgatado, setResgatado] = useState(Boolean(inv?.resgate_data));
  const [isento, setIsento] = useState(Boolean(inv?.isento_ir));
  const form = useRef<HTMLFormElement>(null);
  const fundo = tipo === "fundo";
  const taxa = INDEXADORES.find((i) => i[0] === indexador) ?? INDEXADORES[0];
  const e = estado.erros ?? {};
  const v = estado.valores;
  const inicial = (campo: string, doInv: string | undefined) => (v ? v[campo] : doInv);

  useEffect(() => {
    if (estado.ok && !inv) {
      form.current?.reset();
      setTipo("cdb");
      setIndexador("cdi");
      setResgatado(false);
      setIsento(false);
    }
  }, [estado.ok, inv]);

  return (
    <form ref={form} action={acao} className="grid gap-4" noValidate>
      <input type="hidden" name="carteira" value={carteira} />
      {inv && <input type="hidden" name="investimento" value={inv.id} />}
      {e.form && (
        <p role="alert" className="rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {e.form}
        </p>
      )}
      {estado.ok && !inv && (
        <p role="status" className="rounded-md bg-positivo/10 px-3 py-2 text-sm text-positivo">
          Investimento incluído.
        </p>
      )}
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <div className="grid content-start gap-2">
          <Label htmlFor="tipo-inv">Tipo</Label>
          <select id="tipo-inv" name="tipo" value={tipo} onChange={(ev) => setTipo(ev.target.value)} className={classeSelect}>
            {TIPOS.map(([v, r]) => (
              <option key={v} value={v}>
                {r}
              </option>
            ))}
          </select>
        </div>
        <Campo
          nome="nome"
          rotulo="Nome"
          placeholder={fundo ? "Fundo DI da corretora" : "CDB Banco X 2027"}
          maxLength={80}
          required
          defaultValue={inicial("nome", inv?.nome)}
          erro={e.nome}
          className="col-span-1"
        />
        <Campo nome="data_aplicacao" rotulo="Data da aplicação" type="date" max={hoje} required defaultValue={inicial("data_aplicacao", inv?.data_aplicacao ?? hoje)} erro={e.data_aplicacao} />
        <Campo nome="valor_aplicado" rotulo="Valor aplicado (R$)" inputMode="decimal" placeholder="10.000,00" required defaultValue={inicial("valor_aplicado", br(inv?.valor_aplicado))} erro={e.valor_aplicado} />

        {fundo ? (
          <>
            <Campo nome="cnpj" rotulo="CNPJ do fundo" inputMode="numeric" placeholder="00.000.000/0000-00" required defaultValue={inicial("cnpj", inv?.cnpj ?? undefined)} erro={e.cnpj} />
            <Campo
              nome="cotas"
              rotulo="Cotas (opcional)"
              inputMode="decimal"
              placeholder="Calculadas pela cota do dia"
              defaultValue={inicial("cotas", inv?.cotas_informadas ? br(inv.cotas) : undefined)}
              erro={e.cotas}
            />
          </>
        ) : (
          <>
            <div className="grid content-start gap-2">
              <Label htmlFor="indexador">Rendimento</Label>
              <select id="indexador" name="indexador" value={indexador} onChange={(ev) => setIndexador(ev.target.value)} className={classeSelect}>
                {INDEXADORES.map(([v, r]) => (
                  <option key={v} value={v}>
                    {r}
                  </option>
                ))}
              </select>
            </div>
            <Campo nome="taxa" rotulo={taxa[2]} inputMode="decimal" placeholder={taxa[3]} required defaultValue={inicial("taxa", br(inv?.taxa))} erro={e.taxa} />
            <Campo nome="vencimento" rotulo="Vencimento (opcional)" type="date" defaultValue={inicial("vencimento", inv?.vencimento ?? undefined)} erro={e.vencimento} />
          </>
        )}
      </div>

      <div className="flex flex-wrap gap-x-6 gap-y-2 text-sm">
        {!fundo && (
          <Label className="flex items-center gap-2 font-normal">
            <input
              type="checkbox"
              name="isento_ir"
              checked={tipo === "lci_lca" || isento}
              onChange={(ev) => setIsento(ev.target.checked)}
              disabled={tipo === "lci_lca"}
              className="accent-[var(--azul)]"
            />
            Isento de imposto de renda {tipo === "lci_lca" ? "(LCI e LCA são sempre)" : "(debêntures incentivadas, por exemplo)"}
          </Label>
        )}
        <Label className="flex items-center gap-2 font-normal">
          <input type="checkbox" checked={resgatado} onChange={(ev) => setResgatado(ev.target.checked)} className="accent-[var(--azul)]" />
          Já resgatei
        </Label>
      </div>

      {resgatado && (
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <Campo nome="resgate_data" rotulo="Data do resgate" type="date" max={hoje} required defaultValue={inicial("resgate_data", inv?.resgate_data ?? undefined)} erro={e.resgate_data} />
          <Campo nome="resgate_valor" rotulo="Valor bruto resgatado (R$)" inputMode="decimal" required defaultValue={inicial("resgate_valor", br(inv?.resgate_valor))} erro={e.resgate_valor} />
        </div>
      )}

      <div className="flex flex-wrap items-center gap-2">
        <Button type="submit" disabled={pendente}>
          {pendente ? "Salvando…" : inv ? "Salvar" : "Incluir investimento"}
        </Button>
        {inv && (
          <Button asChild variant="ghost">
            <Link href={`/carteira?c=${carteira}#renda-fixa`}>Cancelar</Link>
          </Button>
        )}
      </div>
      <p className="text-xs text-muted-foreground">
        {fundo
          ? "O valor do fundo vem da cota diária publicada pela CVM (a partir de 2021). Sem o número de cotas, ele é calculado pela cota do dia da aplicação."
          : "O valor é uma estimativa pelo CDI ou IPCA publicados pelo Banco Central. O extrato do banco pode diferir por arredondamentos e taxas."}
      </p>
    </form>
  );
}
