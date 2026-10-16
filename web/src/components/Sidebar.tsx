import { useMemo, useState } from "react";
import { Link, NavLink, useNavigate, useParams } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Database, MessageSquare, MessageSquarePlus, Search, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import { keys, useSessions } from "@/lib/queries";
import { cn, groupByRecency } from "@/lib/utils";
import { Button } from "./ui/button";
import { ConfirmDialog } from "./ui/confirm-dialog";
import { Tooltip } from "./ui/tooltip";
import { LogoMark } from "./Logo";

export function Sidebar({ onNavigate }: { onNavigate?: () => void }) {
  const { sessionId } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { data: sessions, isLoading } = useSessions();
  const [query, setQuery] = useState("");
  const [pendingDelete, setPendingDelete] = useState<{ id: string; title: string } | null>(null);

  const groups = useMemo(() => {
    const q = query.trim().toLowerCase();
    const filtered = (sessions ?? []).filter((s) => !q || s.title.toLowerCase().includes(q));
    return groupByRecency(filtered);
  }, [sessions, query]);

  const remove = useMutation({
    mutationFn: (id: string) => api.deleteSession(id),
    onSuccess: (_, id) => {
      queryClient.setQueryData(keys.sessions, (old: typeof sessions) => old?.filter((s) => s.session_id !== id));
      queryClient.removeQueries({ queryKey: keys.messages(id) });
      if (id === sessionId) navigate("/");
      toast.success("Conversation deleted");
      setPendingDelete(null);
    },
    onError: (e: Error) => toast.error(e.message),
  });

  return (
    <div className="flex h-full flex-col bg-sidebar">
      <div className="flex h-14 items-center gap-2.5 px-4">
        <LogoMark />
        <div className="leading-tight">
          <div className="text-sm font-semibold">CloudMind</div>
          <div className="text-[11px] text-muted-foreground">AWS Intelligence Platform</div>
        </div>
      </div>

      <div className="space-y-2 px-3 pb-3">
        <Button asChild className="w-full justify-start" variant="outline">
          <Link to="/" onClick={onNavigate}>
            <MessageSquarePlus /> New conversation
          </Link>
        </Button>
        <div className="relative">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search conversations"
            aria-label="Search conversations"
            className="h-8 w-full rounded-md border bg-background pl-8 pr-2 text-sm placeholder:text-muted-foreground focus-visible:ring-2"
          />
        </div>
      </div>

      <nav className="scrollbar-thin flex-1 overflow-y-auto px-2 pb-2" aria-label="Conversations">
        {isLoading && (
          <div className="space-y-2 px-2 pt-2">
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="h-7 animate-pulse rounded-md bg-muted" />
            ))}
          </div>
        )}
        {!isLoading && groups.length === 0 && (
          <p className="px-3 py-6 text-center text-xs text-muted-foreground">
            {query ? "No matching conversations" : "No conversations yet"}
          </p>
        )}
        {groups.map((group) => (
          <div key={group.label} className="mb-3">
            <div className="px-3 pb-1 pt-2 text-[11px] font-medium uppercase tracking-wider text-muted-foreground">{group.label}</div>
            <ul>
              {group.items.map((s) => (
                <li key={s.session_id} className="group relative">
                  <NavLink
                    to={`/c/${s.session_id}`}
                    onClick={onNavigate}
                    className={({ isActive }) =>
                      cn(
                        "flex items-center gap-2 rounded-md py-1.5 pl-3 pr-9 text-sm transition-colors",
                        isActive ? "bg-accent font-medium text-foreground" : "text-muted-foreground hover:bg-accent/60 hover:text-foreground",
                      )
                    }
                  >
                    <MessageSquare className="h-3.5 w-3.5 shrink-0 opacity-60" />
                    <span className="truncate">{s.title}</span>
                  </NavLink>
                  <Tooltip content="Delete">
                    <button
                      onClick={() => setPendingDelete({ id: s.session_id, title: s.title })}
                      aria-label={`Delete conversation ${s.title}`}
                      className="absolute right-1.5 top-1/2 -translate-y-1/2 rounded p-1 text-muted-foreground opacity-0 transition hover:bg-background hover:text-rose-600 focus-visible:opacity-100 group-hover:opacity-100"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </Tooltip>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </nav>

      <div className="border-t p-2">
        <NavLink
          to="/knowledge"
          onClick={onNavigate}
          className={({ isActive }) =>
            cn(
              "flex items-center gap-2 rounded-md px-3 py-2 text-sm transition-colors",
              isActive ? "bg-accent font-medium" : "text-muted-foreground hover:bg-accent/60 hover:text-foreground",
            )
          }
        >
          <Database className="h-4 w-4" /> Knowledge base
        </NavLink>
      </div>

      <ConfirmDialog
        open={!!pendingDelete}
        onOpenChange={(o) => !o && setPendingDelete(null)}
        title="Delete conversation?"
        description={<>“{pendingDelete?.title}” and all its messages will be permanently deleted.</>}
        confirmLabel="Delete"
        pending={remove.isPending}
        onConfirm={() => pendingDelete && remove.mutate(pendingDelete.id)}
      />
    </div>
  );
}
