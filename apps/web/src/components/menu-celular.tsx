"use client";

import { Menu, X } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

/** Menu do cabeçalho em telas pequenas, onde os links não cabem na barra. */
export function MenuCelular({ links }: { links: { href: string; rotulo: string }[] }) {
  const [aberto, setAberto] = useState(false);
  const caminho = usePathname();

  useEffect(() => setAberto(false), [caminho]);
  useEffect(() => {
    if (!aberto) return;
    const fechar = (e: KeyboardEvent) => e.key === "Escape" && setAberto(false);
    window.addEventListener("keydown", fechar);
    return () => window.removeEventListener("keydown", fechar);
  }, [aberto]);

  return (
    <div className="lg:hidden">
      <Button
        type="button"
        variant="ghost"
        size="icon"
        aria-label={aberto ? "Fechar menu" : "Abrir menu"}
        aria-expanded={aberto}
        aria-controls="menu-celular"
        onClick={() => setAberto((a) => !a)}
      >
        {aberto ? <X aria-hidden /> : <Menu aria-hidden />}
      </Button>
      {aberto && (
        <nav
          id="menu-celular"
          aria-label="Menu"
          className="absolute inset-x-0 top-16 max-h-[calc(100dvh-4rem)] overflow-y-auto overscroll-contain border-b bg-background px-4 pb-4 shadow-lg"
        >
          <ul className="mx-auto grid max-w-6xl gap-1 pt-2">
            {links.map((l) => (
              <li key={l.href}>
                <Link
                  href={l.href}
                  aria-current={caminho === l.href ? "page" : undefined}
                  className={cn(
                    "block rounded-lg px-3 py-3 text-base font-medium transition-colors hover:bg-muted",
                    caminho === l.href && "bg-accent text-azul",
                  )}
                >
                  {l.rotulo}
                </Link>
              </li>
            ))}
          </ul>
        </nav>
      )}
    </div>
  );
}
