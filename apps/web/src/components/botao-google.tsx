import { Button } from "@/components/ui/button";
import { entrarComGoogle } from "@/lib/acoes";

export function BotaoGoogle({ voltar }: { voltar?: string }) {
  return (
    <form action={entrarComGoogle}>
      {voltar && <input type="hidden" name="voltar" value={voltar} />}
      <Button type="submit" variant="outline" className="w-full">
        Continuar com Google
      </Button>
    </form>
  );
}
