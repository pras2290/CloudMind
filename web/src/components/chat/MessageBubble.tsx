import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Check, Copy } from "lucide-react";
import type { Message } from "@/lib/api";
import { LogoMark } from "../Logo";
import { SourceBadge } from "../ui/source-badge";
import { Tooltip } from "../ui/tooltip";
import { ConfidenceMeter } from "./ConfidenceMeter";
import { SourcesPanel } from "./SourcesPanel";

export function UserBubble({ content }: { content: string }) {
  return (
    <div className="flex justify-end animate-fade-in">
      <div className="max-w-[85%] whitespace-pre-wrap rounded-2xl rounded-br-md bg-primary px-4 py-2.5 text-sm text-primary-foreground shadow-sm">
        {content}
      </div>
    </div>
  );
}

export function AssistantBubble({ message }: { message: Message }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    await navigator.clipboard.writeText(message.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };
  return (
    <div className="flex gap-3 animate-fade-in">
      <LogoMark className="mt-0.5 h-7 w-7 shrink-0" />
      <div className="min-w-0 flex-1">
        <div className="prose prose-sm prose-slate max-w-none dark:prose-invert prose-pre:bg-slate-900 prose-pre:text-slate-100 prose-table:text-xs">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown>
        </div>
        <div className="mt-2 flex flex-wrap items-center gap-3">
          {message.source && <SourceBadge source={message.source} />}
          {message.confidence != null && <ConfidenceMeter value={message.confidence} />}
          <Tooltip content={copied ? "Copied" : "Copy answer"}>
            <button onClick={copy} aria-label="Copy answer" className="rounded p-1 text-muted-foreground hover:bg-accent hover:text-foreground">
              {copied ? <Check className="h-3.5 w-3.5 text-emerald-500" /> : <Copy className="h-3.5 w-3.5" />}
            </button>
          </Tooltip>
        </div>
        {message.docs && message.docs.length > 0 && <SourcesPanel docs={message.docs} />}
      </div>
    </div>
  );
}

export function ThinkingBubble() {
  return (
    <div className="flex gap-3 animate-fade-in" role="status" aria-live="polite">
      <LogoMark className="mt-0.5 h-7 w-7 shrink-0" />
      <div className="flex items-center gap-2 pt-1 text-sm text-muted-foreground">
        <span className="flex gap-1">
          {[0, 150, 300].map((d) => (
            <span key={d} className="h-1.5 w-1.5 animate-bounce rounded-full bg-primary/70" style={{ animationDelay: `${d}ms` }} />
          ))}
        </span>
        Searching your AWS knowledge base…
      </div>
    </div>
  );
}
