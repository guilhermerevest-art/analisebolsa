import { formatarData, formatarNumero, formatarPreco, NOMES_PROVENTO } from "@/lib/formato";
import type { Proventos } from "@/lib/tipos-api";

const SOCIETARIOS = new Set(["bonificacao", "desdobramento", "grupamento"]);

export function PainelProventos({ dados }: { dados: Proventos | null }) {
  if (!dados || dados.itens.length === 0) return <p className="text-sm text-muted-foreground">Nenhum provento registrado.</p>;
  return (
    <div className="grid gap-8 lg:grid-cols-[1fr_16rem]">
      <div className="max-h-[28rem] overflow-auto">
        <table className="w-full text-sm">
          <thead className="sticky top-0 bg-background text-left text-muted-foreground">
            <tr>
              <th className="py-2 pr-4 font-normal">Tipo</th>
              <th className="py-2 pr-4 font-normal">Data com</th>
              <th className="py-2 pr-4 font-normal">Pagamento</th>
              <th className="py-2 text-right font-normal">Valor</th>
            </tr>
          </thead>
          <tbody>
            {dados.itens.map((p) => (
              <tr key={`${p.tipo}-${p.data_com}`} className="border-t">
                <td className="py-2 pr-4">{NOMES_PROVENTO[p.tipo] ?? p.tipo}</td>
                <td className="py-2 pr-4">{formatarData(p.data_com)}</td>
                <td className="py-2 pr-4">{formatarData(p.data_pagamento)}</td>
                <td className="py-2 text-right tabular-nums">
                  {SOCIETARIOS.has(p.tipo) ? `fator ${formatarNumero(p.valor, 8)}` : formatarPreco(p.valor)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div>
        <h3 className="mb-2 text-sm font-medium">DY por ano</h3>
        <table className="w-full text-sm">
          <thead className="text-left text-muted-foreground">
            <tr>
              <th className="py-2 font-normal">Ano</th>
              <th className="py-2 text-right font-normal">R$/cota</th>
              <th className="py-2 text-right font-normal">DY</th>
            </tr>
          </thead>
          <tbody>
            {dados.dy_por_ano.map((a) => (
              <tr key={a.ano} className="border-t">
                <td className="py-2">{a.ano}</td>
                <td className="py-2 text-right tabular-nums">{formatarNumero(a.total, 4)}</td>
                <td className="py-2 text-right tabular-nums">{a.dy === null ? "—" : `${formatarNumero(a.dy)}%`}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="mt-2 text-xs text-muted-foreground">DY = proventos em dinheiro do ano ÷ último fechamento do ano.</p>
      </div>
    </div>
  );
}
