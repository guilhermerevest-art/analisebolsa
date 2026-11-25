import { cn } from "@/lib/utils";

/** Faixa que rola na horizontal (inspirada no Marquee do Magic UI). Pausa no hover. */
export function Marquee({ children, className, segundos = 40 }: { children: React.ReactNode; className?: string; segundos?: number }) {
  return (
    <div className={cn("group flex overflow-hidden [--gap:2rem] [mask-image:linear-gradient(to_right,transparent,black_8%,black_92%,transparent)]", className)}>
      {[0, 1].map((i) => (
        <div
          key={i}
          aria-hidden={i === 1}
          className="flex shrink-0 animate-[marquee_var(--duracao)_linear_infinite] items-center gap-[var(--gap)] pr-[var(--gap)] group-hover:[animation-play-state:paused] motion-reduce:animate-none"
          style={{ ["--duracao" as string]: `${segundos}s` }}
        >
          {children}
        </div>
      ))}
    </div>
  );
}
