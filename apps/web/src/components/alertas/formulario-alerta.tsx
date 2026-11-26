"use client";

import { startTransition, useActionState, useEffect, useRef, useState } from "react";

import { Campo } from "@/components/campo";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { criarAlerta, type EstadoAlerta } from "@/lib/acoes-alertas";
import { TIPOS_ALERTA } from "@/lib/validacao";
import { classeSelect } from "@/components/ui/select-nativo";

type Tipo = keyof typeof TIPOS_ALERTA;

export function FormularioAlerta({ ticker, sinais, desabilitado }: { ticker: string; sinais: { codigo: string; descricao: string }[]; desabilitado: boolean }) {
  const [estado, acao, pendente] = useActionState<EstadoAlerta, FormData>(criarAlerta, {});
  const [tipo, setTipo] = useState<Tipo>("preco_acima");
  const form = useRef<HTMLFormElement>(null);

  useEffect(() => {
    const parametro = form.current?.querySelector<HTMLInputElement>("[name=parametro]");
    if (estado.ok && parametro) {
      parametro.value = "";
      parametro.focus();
    }
  }, [estado.ok]);

  // Envio manual: com `action={acao}` o React limpa o formulário a cada envio, inclusive
  // quando a validação falha.
  return (
    <form
      ref={form}
      onSubmit={(e) => {
        e.preventDefault();
        const dados = new FormData(e.currentTarget);
        startTransition(() => acao(dados));
      }}
      className="grid gap-4"
      noValidate
    >
      {estado.erros?.form && (
        <p role="alert" className="rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {estado.erros.form}
        </p>
      )}
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-[10rem_16rem_1fr_auto] lg:items-start">
        <Campo nome="ticker" rotulo="Ticker" placeholder="PETR4" defaultValue={ticker} autoCapitalize="characters" autoComplete="off" required erro={estado.erros?.ticker} />
        <div className="grid content-start gap-2">
          <Label htmlFor="tipo">Quando</Label>
          <select id="tipo" name="tipo" value={tipo} onChange={(e) => setTipo(e.target.value as Tipo)} className={classeSelect}>
            {Object.entries(TIPOS_ALERTA).map(([valor, rotulo]) => (
              <option key={valor} value={valor}>
                {rotulo}
              </option>
            ))}
          </select>
        </div>
        {tipo === "insight" ? (
          <div className="grid content-start gap-2">
            <Label htmlFor="codigo">Sinal</Label>
            <select id="codigo" name="codigo" defaultValue="" className={classeSelect} aria-invalid={estado.erros?.codigo ? true : undefined}>
              <option value="" disabled>
                Escolha o sinal
              </option>
              {sinais.map((s) => (
                <option key={s.codigo} value={s.codigo}>
                  {s.descricao[0].toUpperCase() + s.descricao.slice(1)}
                </option>
              ))}
            </select>
            {estado.erros?.codigo && <p className="text-sm text-destructive">{estado.erros.codigo}</p>}
          </div>
        ) : (
          <Campo
            key={tipo}
            nome="parametro"
            rotulo={tipo === "variacao_dia" ? "Variação (%)" : "Preço (R$)"}
            inputMode="decimal"
            placeholder={tipo === "variacao_dia" ? "5" : "40,00"}
            required
            erro={estado.erros?.parametro}
          />
        )}
        <div className="grid content-start gap-2">
          <span aria-hidden className="hidden text-sm lg:block">
            &nbsp;
          </span>
          <Button type="submit" disabled={pendente || desabilitado}>
            {pendente ? "Criando…" : "Criar alerta"}
          </Button>
        </div>
      </div>
    </form>
  );
}
