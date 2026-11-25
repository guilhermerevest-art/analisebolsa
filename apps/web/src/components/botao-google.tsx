import { Button } from "@/components/ui/button";
import { entrarComGoogle } from "@/lib/acoes";

export function BotaoGoogle() {
  return (
    <form action={entrarComGoogle}>
      <Button type="submit" variant="outline" className="w-full">
        Continuar com Google
      </Button>
    </form>
  );
}
