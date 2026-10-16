import { cn, confidenceLevel } from "@/lib/utils";
import { Tooltip } from "../ui/tooltip";

export function ConfidenceMeter({ value }: { value: number }) {
  const pct = Math.round(Math.max(0, Math.min(1, value)) * 100);
  const level = confidenceLevel(value);
  return (
    <Tooltip content="How well the retrieved sources match your question">
      <div className="inline-flex items-center gap-1.5 text-[11px] text-muted-foreground" aria-label={`Confidence ${pct}% (${level.label})`}>
        <div className="h-1.5 w-14 overflow-hidden rounded-full bg-muted" role="meter" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100}>
          <div className={cn("h-full rounded-full transition-all", level.className)} style={{ width: `${pct}%` }} />
        </div>
        <span className="tabular-nums">{pct}%</span>
        <span className="hidden sm:inline">· {level.label}</span>
      </div>
    </Tooltip>
  );
}
