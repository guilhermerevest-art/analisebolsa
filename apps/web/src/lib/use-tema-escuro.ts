"use client";

import { useEffect, useState } from "react";

/** Acompanha o tema do sistema, para as cores dos gráficos. */
export function useTemaEscuro(): boolean {
  const [escuro, setEscuro] = useState(false);
  useEffect(() => {
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    setEscuro(mq.matches);
    const ouvir = (e: MediaQueryListEvent) => setEscuro(e.matches);
    mq.addEventListener("change", ouvir);
    return () => mq.removeEventListener("change", ouvir);
  }, []);
  return escuro;
}
