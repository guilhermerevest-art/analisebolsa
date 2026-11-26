"use client";

import { RefreshCw } from "lucide-react";
import { startTransition, useActionState, useCallback, useEffect, useState } from "react";

import { Campo } from "@/components/campo";
import { Button } from "@/components/ui/button";
import { lerEstadoWhatsapp, removerWhatsappAdmin, salvarWhatsapp, testarWhatsappAdmin, type EstadoForm } from "@/lib/acoes-admin";
import type { ConfigWhatsApp, EstadoInstancia } from "@/lib/tipos-api";
import { cn } from "@/lib/utils";

const ESTADOS: Record<string, { rotulo: string; classe: string }> = {
  open: { rotulo: "Conectada", classe: "bg-positivo/12 text-positivo" },
  connecting: { rotulo: "Aguardando leitura do QR code", classe: "bg-amber-500/15 text-amber-700 dark:text-amber-400" },
  close: { rotulo: "Desconectada", classe: "bg-destructive/10 text-destructive" },
  erro: { rotulo: "Sem resposta da Evolution API", classe: "bg-destructive/10 text-destructive" },
};

function Aviso({ estado }: { estado: EstadoForm }) {
  if (estado.erro)
    return (
      <p role="alert" className="text-sm text-destructive">
        {estado.erro}
      </p>
    );
  if (estado.mensagem)
    return (
      <p role="status" className="text-sm text-positivo">
        {estado.mensagem}
      </p>
    );
  return null;
}

const enviar = (acao: (f: FormData) => void) => (e: React.FormEvent<HTMLFormElement>) => {
  e.preventDefault();
  const dados = new FormData(e.currentTarget);
  startTransition(() => acao(dados));
};

export function WhatsAppEvolution({ config }: { config: ConfigWhatsApp }) {
  const [salvo, salvar, salvando] = useActionState<EstadoForm, FormData>(salvarWhatsapp, {});
  const [teste, testar, testando] = useActionState<EstadoForm, FormData>(testarWhatsappAdmin, {});
  const [estado, setEstado] = useState<EstadoInstancia | null>(null);
  const [consultando, setConsultando] = useState(false);

  const consultar = useCallback(async () => {
    setConsultando(true);
    setEstado(await lerEstadoWhatsapp());
    setConsultando(false);
  }, []);

  // A chave nunca volta para a tela: depois de salvar, o campo fica vazio.
  useEffect(() => {
    const campo = document.getElementById("chave") as HTMLInputElement | null;
    if (salvo.ok && campo) campo.value = "";
  }, [salvo.ok]);

  useEffect(() => {
    if (config.configurada) void consultar();
  }, [config.configurada, config.atualizado_em, consultar]);

  // Enquanto espera a leitura do QR code, confere a conexão a cada 5 segundos.
  useEffect(() => {
    if (!estado || estado.estado === "open" || estado.estado === "erro") return;
    const t = setTimeout(() => void consultar(), 5000);
    return () => clearTimeout(t);
  }, [estado, consultar]);

  const info = estado ? (ESTADOS[estado.estado] ?? { rotulo: estado.estado, classe: "bg-muted text-muted-foreground" }) : null;
  const usando = config.provedor_em_uso === "evolution" ? "Evolution API (esta instância)" : config.provedor_em_uso === "meta" ? "Cloud API da Meta" : "nenhum";

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,22rem)]">
      <form onSubmit={enviar(salvar)} className="grid content-start gap-4 self-start rounded-xl border bg-card p-5" noValidate>
        <div>
          <h3 className="font-semibold">Instância</h3>
          <p className="text-sm text-muted-foreground">Os alertas e os códigos de confirmação saem por este WhatsApp. Canal em uso agora: {usando}.</p>
        </div>
        <Campo nome="url" rotulo="URL da Evolution API" placeholder="https://evolution.seudominio.com" defaultValue={config.url ?? ""} inputMode="url" autoComplete="off" required />
        <Campo nome="instancia" rotulo="Nome da instância" placeholder="analisebolsa" defaultValue={config.instancia ?? ""} autoComplete="off" required />
        <Campo
          nome="chave"
          rotulo={config.chave_final ? `API key (guardada: ${config.chave_final}; deixe vazio para manter)` : "API key"}
          type="password"
          autoComplete="new-password"
          placeholder={config.chave_final ? "••••••••" : "apikey da instância ou a global"}
        />
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" name="ativo" defaultChecked={config.configurada ? config.ativo : true} className="size-4 accent-[var(--azul)]" />
          Usar esta instância para os alertas
        </label>
        <div className="flex flex-wrap items-center gap-3">
          <Button type="submit" disabled={salvando}>
            {salvando ? "Salvando…" : "Salvar"}
          </Button>
          {config.configurada && (
            <Button type="button" variant="ghost" onClick={() => confirm("Remover a instância? Os alertas por WhatsApp param até cadastrar outra.") && startTransition(() => removerWhatsappAdmin())}>
              Remover
            </Button>
          )}
        </div>
        <Aviso estado={salvo} />
      </form>

      <div className="grid content-start gap-4">
        <div className="grid gap-3 rounded-xl border bg-card p-5">
          <div className="flex items-center justify-between gap-2">
            <h3 className="font-semibold">Conexão</h3>
            {config.configurada && (
              <Button type="button" variant="ghost" size="icon" className="size-8" onClick={() => void consultar()} disabled={consultando} title="Atualizar">
                <RefreshCw aria-hidden className={cn(consultando && "animate-spin")} />
                <span className="sr-only">Atualizar o estado da conexão</span>
              </Button>
            )}
          </div>
          {!config.configurada ? (
            <p className="text-sm text-muted-foreground">Salve a instância para ver a conexão.</p>
          ) : !estado ? (
            <p className="text-sm text-muted-foreground">{consultando ? "Consultando…" : "Não foi possível consultar."}</p>
          ) : (
            <>
              <p aria-live="polite">
                <span className={cn("rounded-full px-2.5 py-0.5 text-xs font-medium", info?.classe)}>{info?.rotulo}</span>
              </p>
              {estado.erro && <p className="break-words text-xs text-muted-foreground">{estado.erro}</p>}
              {estado.qr && (
                <div className="grid justify-items-center gap-2">
                  {/* eslint-disable-next-line @next/next/no-img-element -- data URL gerada pela Evolution */}
                  <img src={estado.qr} alt="QR code para conectar o WhatsApp da instância" className="size-56 rounded-lg border bg-white p-2" />
                  <p className="text-center text-xs text-muted-foreground">
                    No celular do número de envio: WhatsApp, Aparelhos conectados, Conectar um aparelho.
                  </p>
                  {estado.codigo_pareamento && (
                    <p className="text-sm">
                      Ou use o código <span className="font-mono font-semibold tracking-wider">{estado.codigo_pareamento}</span>
                    </p>
                  )}
                </div>
              )}
            </>
          )}
        </div>

        {config.configurada && (
          <form onSubmit={enviar(testar)} className="grid gap-3 rounded-xl border bg-card p-5" noValidate>
            <h3 className="font-semibold">Mensagem de teste</h3>
            <Campo nome="numero" rotulo="Enviar para" placeholder="(11) 98765-4321" inputMode="tel" autoComplete="tel-national" />
            <Button type="submit" variant="outline" disabled={testando}>
              {testando ? "Enviando…" : "Enviar teste"}
            </Button>
            <Aviso estado={teste} />
          </form>
        )}
      </div>
    </div>
  );
}
