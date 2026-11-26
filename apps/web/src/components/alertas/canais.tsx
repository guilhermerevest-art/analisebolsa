"use client";

import { BellRing, Check, MessageCircle, Smartphone, Trash2 } from "lucide-react";
import { startTransition, useActionState, useEffect, useState } from "react";

import { Campo } from "@/components/campo";
import { Button } from "@/components/ui/button";
import {
  alternarWhatsapp,
  cadastrarWhatsapp,
  cancelarPush,
  confirmarWhatsapp,
  registrarPush,
  removerAparelho,
  removerWhatsapp,
  testarPush,
  type EstadoCanal,
} from "@/lib/acoes-notificacoes";
import { formatarData } from "@/lib/formato";
import type { Notificacoes } from "@/lib/tipos-api";
import { cn } from "@/lib/utils";

/** Seção "Onde avisar" da página de alertas: push neste aparelho e WhatsApp. */
export function CanaisNotificacao({ estado }: { estado: Notificacoes }) {
  return (
    <div className="grid gap-4 md:grid-cols-2">
      <CartaoPush estado={estado.push} />
      <CartaoWhatsApp estado={estado.whatsapp} />
    </div>
  );
}

function Cartao({ icone, titulo, status, children }: { icone: React.ReactNode; titulo: string; status?: React.ReactNode; children: React.ReactNode }) {
  return (
    <div className="grid content-start gap-4 rounded-xl border bg-card p-5">
      <div className="flex items-start justify-between gap-3">
        <h3 className="flex items-center gap-2 font-semibold">
          <span className="flex size-8 items-center justify-center rounded-lg bg-accent text-azul [&_svg]:size-4">{icone}</span>
          {titulo}
        </h3>
        {status}
      </div>
      {children}
    </div>
  );
}

function Selo({ ligado, children }: { ligado: boolean; children: React.ReactNode }) {
  return (
    <span className={cn("rounded-full px-2.5 py-0.5 text-xs font-medium", ligado ? "bg-positivo/12 text-positivo" : "bg-muted text-muted-foreground")}>
      {children}
    </span>
  );
}

function Mensagem({ estado }: { estado: EstadoCanal }) {
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

// Push

type Suporte = "carregando" | "sem-suporte" | "ios-instalar" | "bloqueado" | "pronto";

function chaveParaBytes(base64: string): Uint8Array<ArrayBuffer> {
  const b64 = (base64 + "=".repeat((4 - (base64.length % 4)) % 4)).replace(/-/g, "+").replace(/_/g, "/");
  const bin = atob(b64);
  const saida = new Uint8Array(new ArrayBuffer(bin.length));
  for (let i = 0; i < bin.length; i++) saida[i] = bin.charCodeAt(i);
  return saida;
}

/** O serviço de push do navegador às vezes não responde; sem prazo, o botão ficaria parado. */
function comPrazo<T>(promessa: Promise<T>, ms: number): Promise<T> {
  return Promise.race([promessa, new Promise<T>((_, rejeitar) => setTimeout(() => rejeitar(new Error("prazo")), ms))]);
}

function descreverAparelho(ua: string): string {
  const navegador = /Edg\//.test(ua) ? "Edge" : /Firefox\//.test(ua) ? "Firefox" : /Chrome\//.test(ua) ? "Chrome" : /Safari\//.test(ua) ? "Safari" : "Navegador";
  const sistema = /iPhone|iPad/.test(ua) ? "iPhone" : /Android/.test(ua) ? "Android" : /Windows/.test(ua) ? "Windows" : /Mac OS X/.test(ua) ? "Mac" : /Linux/.test(ua) ? "Linux" : "";
  return sistema ? `${navegador} no ${sistema}` : navegador;
}

function CartaoPush({ estado }: { estado: Notificacoes["push"] }) {
  const [suporte, setSuporte] = useState<Suporte>("carregando");
  const [inscricao, setInscricao] = useState<PushSubscription | null>(null);
  const [resultado, setResultado] = useState<EstadoCanal>({});
  const [ocupado, setOcupado] = useState(false);

  useEffect(() => {
    const ios = /iPhone|iPad/.test(navigator.userAgent);
    const instalado = window.matchMedia("(display-mode: standalone)").matches || (navigator as { standalone?: boolean }).standalone === true;
    if (!("serviceWorker" in navigator) || !("PushManager" in window) || !("Notification" in window)) {
      setSuporte(ios && !instalado ? "ios-instalar" : "sem-suporte");
      return;
    }
    if (Notification.permission === "denied") setSuporte("bloqueado");
    else setSuporte("pronto");
    navigator.serviceWorker
      .getRegistration("/")
      .then((reg) => reg?.pushManager.getSubscription())
      .then((sub) => {
        if (!sub) return;
        setInscricao(sub);
        // Reenvia a inscrição: o servidor pode tê-la apagado, ou o navegador pode tê-la trocado.
        if (estado.disponivel) void registrarPush(sub.toJSON(), descreverAparelho(navigator.userAgent));
      })
      .catch(() => {});
  }, [estado.disponivel]);

  async function ligar() {
    if (!estado.chave_publica) return;
    setOcupado(true);
    setResultado({});
    try {
      const permissao = await Notification.requestPermission();
      if (permissao !== "granted") {
        setSuporte(permissao === "denied" ? "bloqueado" : "pronto");
        return;
      }
      const reg = await navigator.serviceWorker.register("/sw.js", { scope: "/" });
      await navigator.serviceWorker.ready;
      const sub =
        (await reg.pushManager.getSubscription()) ??
        (await comPrazo(reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: chaveParaBytes(estado.chave_publica) }), 20_000));
      const r = await registrarPush(sub.toJSON(), descreverAparelho(navigator.userAgent));
      setResultado(r.erro ? r : { mensagem: "Notificações ligadas neste aparelho." });
      if (!r.erro) setInscricao(sub);
    } catch {
      setResultado({ erro: "O navegador não deixou ligar as notificações. Tente de novo." });
    } finally {
      setOcupado(false);
    }
  }

  async function desligar() {
    if (!inscricao) return;
    setOcupado(true);
    const endpoint = inscricao.endpoint;
    await inscricao.unsubscribe().catch(() => false);
    await cancelarPush(endpoint);
    setInscricao(null);
    setResultado({ mensagem: "Notificações desligadas neste aparelho." });
    setOcupado(false);
  }

  async function testar() {
    setOcupado(true);
    setResultado(await testarPush());
    setOcupado(false);
  }

  const ligadoAqui = inscricao !== null;
  return (
    <Cartao icone={<BellRing />} titulo="Notificação no aparelho" status={estado.disponivel && <Selo ligado={ligadoAqui}>{ligadoAqui ? "Ligada aqui" : "Desligada aqui"}</Selo>}>
      <p className="text-sm text-muted-foreground">Aparece no celular ou no computador, como a de um app, no fim de cada pregão.</p>
      {!estado.disponivel ? (
        <p className="text-sm text-muted-foreground">As notificações ainda não estão disponíveis no site.</p>
      ) : suporte === "ios-instalar" ? (
        <p className="rounded-lg bg-muted px-3 py-2 text-sm">
          No iPhone, as notificações funcionam com o site na tela de início: toque em Compartilhar, depois em Adicionar à Tela de Início, e abra o analisebolsa por lá.
        </p>
      ) : suporte === "sem-suporte" ? (
        <p className="text-sm text-muted-foreground">Este navegador não recebe notificações. Use o Chrome, o Edge, o Firefox ou o Safari.</p>
      ) : suporte === "bloqueado" ? (
        <p className="rounded-lg bg-muted px-3 py-2 text-sm">
          As notificações estão bloqueadas para este site. Libere nas configurações do navegador (o cadeado ao lado do endereço) e recarregue a página.
        </p>
      ) : (
        <div className="flex flex-wrap gap-2">
          {ligadoAqui ? (
            <>
              <Button type="button" variant="outline" size="sm" onClick={testar} disabled={ocupado}>
                Enviar teste
              </Button>
              <Button type="button" variant="ghost" size="sm" onClick={desligar} disabled={ocupado}>
                Desligar neste aparelho
              </Button>
            </>
          ) : (
            <Button type="button" size="sm" onClick={ligar} disabled={ocupado || suporte === "carregando"}>
              Ligar neste aparelho
            </Button>
          )}
        </div>
      )}
      <Mensagem estado={resultado} />
      {estado.aparelhos.length > 0 && (
        <div className="grid gap-1">
          <p className="text-xs text-muted-foreground">Aparelhos que recebem</p>
          <ul className="divide-y rounded-xl border bg-card text-sm">
            {estado.aparelhos.map((a) => (
              <li key={a.id} className="flex items-center gap-3 px-3 py-1.5">
                <Smartphone aria-hidden className="size-4 shrink-0 text-muted-foreground" />
                <span className="min-w-0 flex-1 truncate">{a.aparelho ?? "Aparelho"}</span>
                <span className="text-xs text-muted-foreground">desde {formatarData(a.criado_em)}</span>
                <form action={removerAparelho}>
                  <input type="hidden" name="aparelho" value={a.id} />
                  <Button type="submit" variant="ghost" size="icon" className="size-7" title="Remover aparelho">
                    <Trash2 aria-hidden />
                    <span className="sr-only">Remover {a.aparelho ?? "aparelho"}</span>
                  </Button>
                </form>
              </li>
            ))}
          </ul>
        </div>
      )}
    </Cartao>
  );
}

// WhatsApp

function CartaoWhatsApp({ estado }: { estado: Notificacoes["whatsapp"] }) {
  const [trocando, setTrocando] = useState(false);
  const [envio, enviar, enviando] = useActionState<EstadoCanal, FormData>(cadastrarWhatsapp, {});
  const [confirmacao, confirmar, confirmando] = useActionState<EstadoCanal, FormData>(confirmarWhatsapp, {});

  useEffect(() => {
    if (envio.ok) setTrocando(false);
  }, [envio.ok]);

  const submeter = (acao: (f: FormData) => void) => (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const dados = new FormData(e.currentTarget);
    startTransition(() => acao(dados));
  };

  const status = estado.confirmado ? (
    <Selo ligado={estado.ativo}>{estado.ativo ? "Ligado" : "Pausado"}</Selo>
  ) : estado.telefone ? (
    <Selo ligado={false}>Aguardando código</Selo>
  ) : null;

  const formNumero = (
    <form onSubmit={submeter(enviar)} className="grid gap-3 sm:grid-cols-[1fr_auto] sm:items-start" noValidate>
      <Campo nome="numero" rotulo="Número com DDD" placeholder="(11) 98765-4321" inputMode="tel" autoComplete="tel-national" required erro={envio.erro} />
      <Button type="submit" disabled={enviando} className="sm:mt-[22px]">
        {enviando ? "Enviando…" : "Enviar código"}
      </Button>
    </form>
  );

  return (
    <Cartao icone={<MessageCircle />} titulo="WhatsApp" status={estado.disponivel && status}>
      <p className="text-sm text-muted-foreground">Uma mensagem por pregão com todos os alertas que dispararam.</p>
      {!estado.disponivel ? (
        <p className="text-sm text-muted-foreground">O WhatsApp ainda não está disponível no site.</p>
      ) : !estado.telefone || trocando ? (
        <>
          {formNumero}
          <p className="text-xs text-muted-foreground">Vamos mandar um código pelo WhatsApp para confirmar que o número é seu.</p>
          {trocando && (
            <Button type="button" variant="link" size="sm" className="h-auto w-fit p-0" onClick={() => setTrocando(false)}>
              Cancelar
            </Button>
          )}
        </>
      ) : !estado.confirmado ? (
        <>
          <p className="text-sm">
            Enviamos um código de 6 dígitos para <span className="font-medium tabular-nums">{estado.telefone}</span>. Ele vale por 10 minutos.
          </p>
          <form onSubmit={submeter(confirmar)} className="grid gap-3 sm:grid-cols-[1fr_auto] sm:items-start" noValidate>
            <Campo nome="codigo" rotulo="Código" placeholder="123456" inputMode="numeric" autoComplete="one-time-code" maxLength={6} required erro={confirmacao.erro} />
            <Button type="submit" disabled={confirmando} className="sm:mt-[22px]">
              {confirmando ? "Confirmando…" : "Confirmar"}
            </Button>
          </form>
          <div className="flex flex-wrap gap-x-4 gap-y-1 text-sm">
            <Button type="button" variant="link" size="sm" className="h-auto p-0" onClick={() => setTrocando(true)}>
              Trocar número
            </Button>
          </div>
          <Mensagem estado={envio.ok ? {} : { erro: envio.erro }} />
        </>
      ) : (
        <>
          <p className="flex items-center gap-2 text-sm">
            <Check aria-hidden className="size-4 text-positivo" />
            <span className="font-medium tabular-nums">{estado.telefone}</span>
          </p>
          <div className="flex flex-wrap gap-2">
            <form action={alternarWhatsapp}>
              <input type="hidden" name="ativo" value={estado.ativo ? "0" : "1"} />
              <Button type="submit" variant="outline" size="sm">
                {estado.ativo ? "Pausar" : "Retomar"}
              </Button>
            </form>
            <Button type="button" variant="ghost" size="sm" onClick={() => setTrocando(true)}>
              Trocar número
            </Button>
            <form action={removerWhatsapp}>
              <Button type="submit" variant="ghost" size="sm">
                Remover
              </Button>
            </form>
          </div>
        </>
      )}
    </Cartao>
  );
}
