"use client";

import { FileSpreadsheet } from "lucide-react";
import { startTransition, useActionState, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { importarB3, previaImportacao, type EstadoImportacao } from "@/lib/acoes-importacao";
import { formatarData, formatarNumero, formatarPreco } from "@/lib/formato";
import type { PreviaImportacao } from "@/lib/tipos-api";
import { cn } from "@/lib/utils";

type Linha = PreviaImportacao["linhas"][number];

const SITUACAO: Record<Linha["situacao"], { rotulo: string; classe: string }> = {
  nova: { rotulo: "Entra", classe: "bg-positivo/12 text-positivo" },
  duplicada: { rotulo: "Já lançada", classe: "bg-muted text-muted-foreground" },
  ignorada: { rotulo: "Fica de fora", classe: "bg-amber-500/15 text-amber-700 dark:text-amber-400" },
};

export function ImportadorB3({ carteira }: { carteira: number }) {
  const [arquivo, setArquivo] = useState<File | null>(null);
  const [previa, lerPrevia, lendo] = useActionState<EstadoImportacao, FormData>(previaImportacao, {});
  const [envio, importar, importando] = useActionState<EstadoImportacao, FormData>(importarB3, {});
  const [filtro, setFiltro] = useState<Linha["situacao"] | "todas">("todas");
  const entrada = useRef<HTMLInputElement>(null);

  const dados = (f: File) => {
    const fd = new FormData();
    fd.set("carteira", String(carteira));
    fd.set("arquivo", f);
    return fd;
  };

  const escolher = (f: File | null) => {
    setArquivo(f);
    setFiltro("todas");
    if (f) startTransition(() => lerPrevia(dados(f)));
  };

  const p = previa.previa;
  const linhas = p ? (filtro === "todas" ? p.linhas : p.linhas.filter((l) => l.situacao === filtro)) : [];

  return (
    <div className="grid gap-6">
      <label
        htmlFor="arquivo-b3"
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => {
          e.preventDefault();
          escolher(e.dataTransfer.files[0] ?? null);
        }}
        className="grid cursor-pointer justify-items-center gap-2 rounded-xl border-2 border-dashed bg-card px-6 py-10 text-center transition-colors hover:border-azul focus-within:border-azul"
      >
        <FileSpreadsheet aria-hidden className="size-8 text-azul" />
        <span className="font-medium">{arquivo ? arquivo.name : "Escolha ou arraste o arquivo .xlsx"}</span>
        <span className="text-sm text-muted-foreground">{lendo ? "Lendo a planilha…" : arquivo ? "Escolher outro arquivo" : "Até 2 MB"}</span>
        <input
          ref={entrada}
          id="arquivo-b3"
          type="file"
          accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
          className="sr-only"
          onChange={(e) => escolher(e.target.files?.[0] ?? null)}
        />
      </label>

      {(previa.erro || envio.erro) && (
        <p role="alert" className="rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {envio.erro ?? previa.erro}
        </p>
      )}

      {p && !lendo && (
        <section aria-labelledby="titulo-previa" className="grid gap-4">
          <div className="flex flex-wrap items-end justify-between gap-4">
            <div>
              <h2 id="titulo-previa" className="text-xl font-semibold">
                Prévia
              </h2>
              <p className="text-sm text-muted-foreground" aria-live="polite">
                {p.novas === 1 ? "1 operação nova" : `${formatarNumero(p.novas, 0)} operações novas`}, {formatarNumero(p.duplicadas, 0)} já lançadas e{" "}
                {formatarNumero(p.ignoradas, 0)} fora da importação.
              </p>
            </div>
            <Button
              type="button"
              size="lg"
              disabled={p.novas === 0 || importando || !arquivo}
              onClick={() => arquivo && startTransition(() => importar(dados(arquivo)))}
            >
              {importando ? "Importando…" : p.novas === 0 ? "Nada novo para importar" : `Importar ${p.novas === 1 ? "1 operação" : `${p.novas} operações`}`}
            </Button>
          </div>

          <div role="group" aria-label="Filtrar linhas" className="flex flex-wrap gap-2">
            {(
              [
                ["todas", `Todas (${p.linhas.length})`],
                ["nova", `Entram (${p.novas})`],
                ["duplicada", `Já lançadas (${p.duplicadas})`],
                ["ignorada", `Ficam de fora (${p.ignoradas})`],
              ] as const
            ).map(([valor, rotulo]) => (
              <Button key={valor} type="button" size="sm" variant={filtro === valor ? "default" : "outline"} aria-pressed={filtro === valor} onClick={() => setFiltro(valor)}>
                {rotulo}
              </Button>
            ))}
          </div>

          <ul className="divide-y rounded-xl border bg-card sm:hidden">
            {linhas.map((l) => (
              <li key={l.linha} className={cn("grid gap-1 px-4 py-3 text-sm", l.situacao !== "nova" && "text-muted-foreground")}>
                <div className="flex items-center justify-between gap-3">
                  <span className="font-semibold">{l.ticker ?? "—"}</span>
                  <span className={cn("rounded-full px-2 py-0.5 text-xs font-medium", SITUACAO[l.situacao].classe)}>{SITUACAO[l.situacao].rotulo}</span>
                </div>
                <p className="tabular-nums">
                  {l.tipo === "venda" ? "Venda" : l.tipo === "compra" ? "Compra" : "Operação"} de {l.quantidade ? formatarNumero(l.quantidade, 4) : "—"} a{" "}
                  {l.preco ? formatarPreco(l.preco) : "—"} em {l.data ? formatarData(l.data) : "—"}
                </p>
                {l.motivo && l.situacao === "ignorada" && <p className="text-xs">Linha {l.linha}: {l.motivo}</p>}
              </li>
            ))}
          </ul>

          <div className="hidden overflow-x-auto rounded-xl border bg-card sm:block">
            <table className="w-full text-sm">
              <thead className="border-b text-left text-muted-foreground">
                <tr>
                  <th scope="col" className="px-3 py-2 font-medium">
                    Linha
                  </th>
                  <th scope="col" className="px-3 py-2 font-medium">
                    Data
                  </th>
                  <th scope="col" className="px-3 py-2 font-medium">
                    Operação
                  </th>
                  <th scope="col" className="px-3 py-2 font-medium">
                    Ativo
                  </th>
                  <th scope="col" className="px-3 py-2 text-right font-medium">
                    Quantidade
                  </th>
                  <th scope="col" className="px-3 py-2 text-right font-medium">
                    Preço
                  </th>
                  <th scope="col" className="px-3 py-2 font-medium">
                    Situação
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {linhas.map((l) => (
                  <tr key={l.linha} className={cn(l.situacao !== "nova" && "text-muted-foreground")}>
                    <td className="px-3 py-2 tabular-nums">{l.linha}</td>
                    <td className="px-3 py-2 tabular-nums">{l.data ? formatarData(l.data) : "—"}</td>
                    <td className="px-3 py-2">{l.tipo === "compra" ? "Compra" : l.tipo === "venda" ? "Venda" : "—"}</td>
                    <td className="px-3 py-2 font-medium">{l.ticker ?? "—"}</td>
                    <td className="px-3 py-2 text-right tabular-nums">{l.quantidade ? formatarNumero(l.quantidade, 4) : "—"}</td>
                    <td className="px-3 py-2 text-right tabular-nums">{l.preco ? formatarPreco(l.preco) : "—"}</td>
                    <td className="px-3 py-2">
                      <span className={cn("whitespace-nowrap rounded-full px-2 py-0.5 text-xs font-medium", SITUACAO[l.situacao].classe)}>{SITUACAO[l.situacao].rotulo}</span>
                      {l.motivo && l.situacao === "ignorada" && <span className="ml-2 text-xs">{l.motivo}</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  );
}
