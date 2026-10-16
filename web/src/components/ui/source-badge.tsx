import { cn, sourceMeta } from "@/lib/utils";

export function SourceBadge({ source, className }: { source: string | null | undefined; className?: string }) {
  const meta = sourceMeta(source);
  return (
    <span className={cn("inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium ring-1 ring-inset", meta.className, className)}>
      {meta.label}
    </span>
  );
}
