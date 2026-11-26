import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

type Props = React.ComponentProps<"input"> & { nome: string; rotulo: string; erro?: string };

export function Campo({ nome, rotulo, erro, ...props }: Props) {
  const idErro = `${nome}-erro`;
  return (
    <div className="grid content-start gap-2">
      <Label htmlFor={nome}>{rotulo}</Label>
      <Input
        id={nome}
        name={nome}
        aria-invalid={erro ? true : undefined}
        aria-describedby={erro ? idErro : undefined}
        {...props}
      />
      {erro && (
        <p id={idErro} className="text-sm text-destructive">
          {erro}
        </p>
      )}
    </div>
  );
}
