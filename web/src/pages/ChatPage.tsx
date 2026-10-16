import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertCircle, RotateCw } from "lucide-react";
import { api, type ChatResponse, type Message } from "@/lib/api";
import { keys, useKBStatus } from "@/lib/queries";
import { newId } from "@/lib/utils";
import { AssistantBubble, ThinkingBubble, UserBubble } from "@/components/chat/MessageBubble";
import { Composer } from "@/components/chat/Composer";
import { EmptyState } from "@/components/chat/EmptyState";
import { Button } from "@/components/ui/button";

type Pending = { text: string; sessionId: string };

export default function ChatPage() {
  const { sessionId } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { data: kb } = useKBStatus();
  const bottomRef = useRef<HTMLDivElement>(null);
  const [pending, setPending] = useState<Pending | null>(null);

  const messages = useQuery({
    queryKey: keys.messages(sessionId ?? ""),
    queryFn: () => api.messages(sessionId!),
    enabled: !!sessionId,
    staleTime: Infinity,
  });

  const send = useMutation({
    mutationFn: ({ text, sessionId }: Pending) => api.chat(text, sessionId),
    onSuccess: (res: ChatResponse, vars) => {
      const now = new Date().toISOString();
      const added: Message[] = [
        { role: "user", content: vars.text, timestamp: now, source: null, confidence: null },
        { role: "assistant", content: res.answer, timestamp: now, source: res.source, confidence: res.confidence, docs: res.docs },
      ];
      queryClient.setQueryData<Message[]>(keys.messages(res.session_id), (old) => [...(old ?? []), ...added]);
      queryClient.invalidateQueries({ queryKey: keys.sessions });
      setPending(null);
      if (sessionId !== res.session_id) navigate(`/c/${res.session_id}`, { replace: !sessionId });
    },
  });

  // Reset transient state when switching conversations.
  useEffect(() => {
    setPending(null);
    send.reset();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId]);

  const submit = (text: string) => {
    const p = { text, sessionId: sessionId ?? newId() };
    setPending(p);
    send.mutate(p);
  };

  const history = sessionId ? messages.data ?? [] : [];
  const showEmpty = !sessionId && !pending;

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [history.length, pending, send.isError]);

  const kbReady = kb?.ready ?? true;

  return (
    <div className="flex h-full flex-col">
      <div className="scrollbar-thin min-h-0 flex-1 overflow-y-auto">
        {showEmpty ? (
          <EmptyState onPick={submit} kbReady={kbReady} />
        ) : (
          <div className="mx-auto max-w-3xl space-y-6 px-4 py-6">
            {messages.isLoading && (
              <div className="space-y-4">
                <div className="ml-auto h-10 w-1/2 animate-pulse rounded-2xl bg-muted" />
                <div className="h-20 w-3/4 animate-pulse rounded-2xl bg-muted" />
              </div>
            )}
            {messages.isError && (
              <ErrorCard message="Couldn't load this conversation." onRetry={() => messages.refetch()} />
            )}
            {history.map((m, i) => (m.role === "user" ? <UserBubble key={i} content={m.content} /> : <AssistantBubble key={i} message={m} />))}
            {pending && <UserBubble content={pending.text} />}
            {pending && send.isPending && <ThinkingBubble />}
            {pending && send.isError && <ErrorCard message={send.error.message} onRetry={() => send.mutate(pending)} />}
            <div ref={bottomRef} />
          </div>
        )}
      </div>
      <Composer
        onSend={submit}
        busy={send.isPending}
        disabled={!kbReady}
        placeholder={kbReady ? undefined : "Refresh AWS data on the Knowledge base page to start chatting"}
      />
    </div>
  );
}

function ErrorCard({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div role="alert" className="flex items-center gap-3 rounded-lg border border-rose-500/30 bg-rose-500/10 p-3 text-sm animate-fade-in">
      <AlertCircle className="h-4 w-4 shrink-0 text-rose-600" />
      <span className="flex-1">{message}</span>
      <Button size="sm" variant="outline" onClick={onRetry}>
        <RotateCw /> Retry
      </Button>
    </div>
  );
}
