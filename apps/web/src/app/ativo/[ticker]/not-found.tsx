import Link from "next/link";

export default function AtivoNaoEncontrado() {
  return (
    <div className="mx-auto max-w-md py-16 text-center">
      <h1 className="text-2xl font-semibold tracking-tight">Ativo não encontrado</h1>
      <p className="mt-2 text-muted-foreground">Confira o código de negociação ou use a busca (Ctrl+K).</p>
      <Link href="/" className="mt-6 inline-block underline underline-offset-4">
        Voltar ao início
      </Link>
    </div>
  );
}
