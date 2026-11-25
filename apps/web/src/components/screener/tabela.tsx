import { ArrowDown, ArrowUp } from "lucide-react";
import Link from "next/link";

import { classeVariacao, formatarCompacto, formatarNumero, formatarPct, formatarPreco } from "@/lib/formato";
import { proximaOrdem, urlCom } from "@/lib/screener";
import type { ItemScreener } from "@/lib/tipos-api";
import { cn } from "@/lib/utils";

type Busca = Record<string, string | string[] | undefined>;

type Coluna = {
  chave: string;
  rotulo: string;
  titulo?: string;
  render: (i: ItemScreener) => React.ReactNode;
  classe?: string;
};

const NOMES_TENDENCIA = { alta: "Alta", baixa: "Baixa", lateral: "Lateral" } as const;
const CLASSE_TENDENCIA = { alta: "text-positivo", baixa: "text-destructive", lateral: "text-muted-foreground" } as const;

const variacao = (v: number | null) => <span className={classeVariacao(v)}>{formatarPct(v)}</span>;
const pct = (v: number | null) => (v === null ? "—" : `${formatarNumero(v)}%`);

export const COLUNAS: Coluna[] = [
  { chave: "preco", rotulo: "Preço", render: (i) => formatarPreco(i.preco) },
  { chave: "var_1d", rotulo: "Dia", render: (i) => variacao(i.var_1d) },
  { chave: "var_12m", rotulo: "12 meses", render: (i) => variacao(i.var_12m) },
  {
    chave: "tendencia",
    rotulo: "Tendência",
    render: (i) => (i.tendencia ? <span className={CLASSE_TENDENCIA[i.tendencia]}>{NOMES_TENDENCIA[i.tendencia]}</span> : "—"),
  },
  { chave: "pos_52s", rotulo: "52 sem.", titulo: "Posição entre a mínima (0%) e a máxima (100%) de 52 semanas", render: (i) => pct(i.pos_52s), classe: "hidden md:table-cell" },
  { chave: "rsi14", rotulo: "RSI", render: (i) => formatarNumero(i.rsi14, 0), classe: "hidden lg:table-cell" },
  { chave: "dy_12m", rotulo: "DY", titulo: "Dividend yield de 12 meses", render: (i) => pct(i.dy_12m) },
  { chave: "pl", rotulo: "P/L", render: (i) => formatarNumero(i.pl, 1), classe: "hidden sm:table-cell" },
  { chave: "pvp", rotulo: "P/VP", render: (i) => formatarNumero(i.pvp, 2), classe: "hidden md:table-cell" },
  { chave: "volume_financeiro_20d", rotulo: "Liquidez", titulo: "Volume financeiro médio diário em 20 pregões", render: (i) => (i.volume_financeiro_20d === null ? "—" : `R$ ${formatarCompacto(i.volume_financeiro_20d)}`), classe: "hidden sm:table-cell" },
];

function Cabecalho({ chave, rotulo, titulo, ordem, busca, classe }: { chave: string; rotulo: string; titulo?: string; ordem: string; busca: Busca; classe?: string }) {
  const ordenavel = chave !== "tendencia";
  const ativa = ordem.replace(/^-/, "") === chave;
  const conteudo = (
    <>
      {rotulo}
      {ativa && (ordem.startsWith("-") ? <ArrowDown className="size-3" aria-hidden /> : <ArrowUp className="size-3" aria-hidden />)}
    </>
  );
  return (
    <th
      scope="col"
      title={titulo}
      aria-sort={ativa ? (ordem.startsWith("-") ? "descending" : "ascending") : undefined}
      className={cn("whitespace-nowrap py-2 pl-3 text-right font-normal", chave === "ticker" && "pl-0 text-left", classe)}
    >
      {ordenavel ? (
        <Link href={urlCom(busca, { ordem: proximaOrdem(ordem, chave) })} className={cn("inline-flex items-center gap-1 hover:text-foreground", ativa && "text-foreground")}>
          {conteudo}
        </Link>
      ) : (
        conteudo
      )}
    </th>
  );
}

export function TabelaScreener({ itens, ordem, busca }: { itens: ItemScreener[]; ordem: string; busca: Busca }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead className="text-muted-foreground">
          <tr>
            <Cabecalho chave="ticker" rotulo="Ativo" ordem={ordem} busca={busca} />
            {COLUNAS.map((c) => (
              <Cabecalho key={c.chave} chave={c.chave} rotulo={c.rotulo} titulo={c.titulo} ordem={ordem} busca={busca} classe={c.classe} />
            ))}
          </tr>
        </thead>
        <tbody>
          {itens.map((i) => (
            <tr key={i.ticker} className="border-t hover:bg-muted/40">
              <td className="py-2 pr-3">
                <Link href={`/ativo/${i.ticker}`} className="font-semibold hover:underline">
                  {i.ticker}
                </Link>
                <span className="block max-w-48 truncate text-xs text-muted-foreground">{i.nome}</span>
              </td>
              {COLUNAS.map((c) => (
                <td key={c.chave} className={cn("whitespace-nowrap py-2 pl-3 text-right tabular-nums", c.classe)}>
                  {c.render(i)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
