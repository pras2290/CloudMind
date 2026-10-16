import { Link } from "react-router-dom";
import { Loader2 } from "lucide-react";
import { useKBStatus } from "@/lib/queries";
import { relativeTime } from "@/lib/utils";
import { Tooltip } from "./ui/tooltip";

export function KBStatusPill() {
  const { data, isError } = useKBStatus();
  let dot = "bg-slate-400";
  let label = "Checking…";
  if (isError) {
    dot = "bg-rose-500";
    label = "API offline";
  } else if (data?.job) {
    label = "Indexing…";
  } else if (data) {
    dot = data.ready ? "bg-emerald-500" : "bg-amber-500";
    label = data.ready ? `${data.total.toLocaleString()} chunks` : "Knowledge base empty";
  }
  const tip = data?.ready ? `Last refreshed ${relativeTime(data.last_refreshed).toLowerCase()}` : "Open knowledge base";
  return (
    <Tooltip content={tip} side="bottom">
      <Link
        to="/knowledge"
        className="inline-flex items-center gap-2 rounded-full border bg-card px-3 py-1 text-xs font-medium text-muted-foreground transition-colors hover:text-foreground"
      >
        {data?.job ? <Loader2 className="h-3 w-3 animate-spin text-primary" /> : <span className={`h-2 w-2 rounded-full ${dot}`} />}
        {label}
      </Link>
    </Tooltip>
  );
}
