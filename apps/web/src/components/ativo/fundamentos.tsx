import { formatarCompacto, formatarData, formatarNumero } from "@/lib/formato";
import type { Fundamentos } from "@/lib/tipos-api";

const METRICAS = [
  { chave: "pl", rotulo: "P/L" },
  { chave: "pvp", rotulo: "P/VP" },
  { chave: "dy_12m", rotulo: "DY 12m", sufixo: "%" },
  { chave: "roe", rotulo: "ROE", sufixo: "%" },
  { chave: "margem_liquida", rotulo: "Margem líquida", sufixo: "%" },
  { chave: "div_liq_ebitda", rotulo: "Dív. líq./EBITDA" },
  { chave: "vpa", rotulo: "VPA", prefixo: "R$ " },
  { chave: "lpa", rotulo: "LPA", prefixo: "R$ " },
] as const;

export function PainelFundamentos({ dados }: { dados: Fundamentos | null }) {
  const u = dados?.ultimo;
  if (!u) return <p className="text-sm text-muted-foreground">Ainda não há fundamentos para este ativo.</p>;
  return (
    <div className="grid gap-6">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
        {METRICAS.map((m) => {
          const valor = u[m.chave];
          return (
            <div key={m.chave} className="rounded-lg border p-4">
              <p className="text-xs text-muted-foreground">{m.rotulo}</p>
              <p className="mt-1 text-lg font-semibold tabular-nums">
                {valor === null || valor === undefined ? "—" : `${"prefixo" in m ? m.prefixo : ""}${formatarNumero(valor)}${"sufixo" in m ? m.sufixo : ""}`}
              </p>
            </div>
          );
        })}
        <div className="rounded-lg border p-4">
          <p className="text-xs text-muted-foreground">Valor de mercado</p>
          <p className="mt-1 text-lg font-semibold tabular-nums">{u.valor_mercado ? `R$ ${formatarCompacto(u.valor_mercado)}` : "—"}</p>
        </div>
      </div>
      <p className="text-xs text-muted-foreground">Referência: {formatarData(u.data_referencia)}</p>
      {dados.historico.length > 1 && (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <caption className="mb-2 text-left font-medium">Histórico</caption>
            <thead className="text-left text-muted-foreground">
              <tr>
                <th className="py-2 pr-4 font-normal">Data</th>
                {METRICAS.slice(0, 5).map((m) => (
                  <th key={m.chave} className="py-2 pr-4 text-right font-normal">
                    {m.rotulo}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {dados.historico.map((h) => (
                <tr key={h.data_referencia} className="border-t">
                  <td className="py-2 pr-4">{formatarData(h.data_referencia)}</td>
                  {METRICAS.slice(0, 5).map((m) => (
                    <td key={m.chave} className="py-2 pr-4 text-right tabular-nums">
                      {formatarNumero(h[m.chave])}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
