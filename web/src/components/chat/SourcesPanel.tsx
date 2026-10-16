import { useState } from "react";
import * as Collapsible from "@radix-ui/react-collapsible";
import { ChevronRight, FileText } from "lucide-react";
import type { SourceDoc } from "@/lib/api";
import { cn } from "@/lib/utils";
import { SourceBadge } from "../ui/source-badge";

export function SourcesPanel({ docs }: { docs: SourceDoc[] }) {
  const [open, setOpen] = useState(false);
  return (
    <Collapsible.Root open={open} onOpenChange={setOpen} className="mt-3">
      <Collapsible.Trigger className="inline-flex items-center gap-1 rounded text-xs font-medium text-muted-foreground hover:text-foreground">
        <ChevronRight className={cn("h-3.5 w-3.5 transition-transform", open && "rotate-90")} />
        {docs.length} retrieved {docs.length === 1 ? "source" : "sources"}
      </Collapsible.Trigger>
      <Collapsible.Content className="mt-2 grid gap-2 animate-fade-in sm:grid-cols-2">
        {docs.map((doc, i) => (
          <div key={i} className="rounded-lg border bg-muted/40 p-3 text-xs">
            <div className="mb-1.5 flex items-center gap-2">
              <FileText className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
              <span className="truncate font-medium">{doc.title ?? doc.type ?? "Document"}</span>
              <SourceBadge source={doc.source} className="ml-auto shrink-0" />
            </div>
            <p className="line-clamp-4 whitespace-pre-line text-muted-foreground">{doc.snippet}</p>
          </div>
        ))}
      </Collapsible.Content>
    </Collapsible.Root>
  );
}
