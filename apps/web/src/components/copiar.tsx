"use client";

import { Check, Copy } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";

/** Botão que copia um texto e confirma por 2 segundos. */
export function Copiar({ texto, rotulo = "Copiar" }: { texto: string; rotulo?: string }) {
  const [copiado, setCopiado] = useState(false);
  return (
    <Button
      type="button"
      variant="outline"
      size="sm"
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(texto);
          setCopiado(true);
          setTimeout(() => setCopiado(false), 2000);
        } catch {
          setCopiado(false);
        }
      }}
    >
      {copiado ? <Check aria-hidden /> : <Copy aria-hidden />}
      <span aria-live="polite">{copiado ? "Copiado" : rotulo}</span>
    </Button>
  );
}
