import Link from "next/link";

import { cn } from "@/lib/utils";

/** Grade de funcionalidades (inspirada no BentoGrid do Magic UI). */
export function BentoGrid({ children, className }: { children: React.ReactNode; className?: string }) {
  return <div className={cn("grid auto-rows-[11rem] grid-cols-1 gap-4 md:grid-cols-3", className)}>{children}</div>;
}

export function BentoCard({
  titulo,
  descricao,
  icone,
  emBreve,
  href,
  className,
}: {
  titulo: string;
  descricao: string;
  icone: React.ReactNode;
  emBreve?: boolean;
  href?: string;
  className?: string;
}) {
  const conteudo = (
    <div
      className={cn(
        "relative flex flex-col justify-end gap-2 overflow-hidden rounded-xl border bg-card p-6 transition-colors hover:bg-accent/40",
        emBreve && "opacity-70",
        className,
      )}
    >
      <div className="absolute right-5 top-5 text-muted-foreground [&_svg]:size-8">{icone}</div>
      <h3 className="font-semibold">
        {titulo}
        {emBreve && <span className="ml-2 rounded-full border px-2 py-0.5 text-[10px] font-medium uppercase text-muted-foreground">em breve</span>}
      </h3>
      <p className="text-sm text-muted-foreground">{descricao}</p>
    </div>
  );
  return href ? (
    <Link href={href} className="contents">
      {conteudo}
    </Link>
  ) : (
    conteudo
  );
}
