import { Link } from "react-router-dom";
import { Database, DollarSign, HardDrive, Server, ShieldAlert } from "lucide-react";
import { LogoMark } from "../Logo";
import { Button } from "../ui/button";

const EXAMPLES = [
  { icon: Server, title: "How many EC2 instances are running?", hint: "Compute inventory" },
  { icon: HardDrive, title: "List all S3 buckets", hint: "Storage overview" },
  { icon: ShieldAlert, title: "Which IAM users don't have MFA enabled?", hint: "Security posture" },
  { icon: DollarSign, title: "What is my AWS cost this month?", hint: "Spend & forecast" },
];

export function EmptyState({ onPick, kbReady }: { onPick: (q: string) => void; kbReady: boolean }) {
  return (
    <div className="mx-auto flex h-full max-w-3xl flex-col items-center justify-center px-4 py-10 text-center">
      <LogoMark className="h-12 w-12 rounded-xl" />
      <h2 className="mt-5 text-2xl font-semibold tracking-tight">How can I help with your AWS today?</h2>
      <p className="mt-2 max-w-md text-sm text-muted-foreground">
        Ask about EC2, S3, Lambda, CloudWatch, IAM, costs, or your uploaded runbooks.
      </p>
      {!kbReady && (
        <div className="mt-6 flex w-full max-w-lg items-center gap-3 rounded-lg border border-amber-500/30 bg-amber-500/10 p-3 text-left text-sm">
          <Database className="h-5 w-5 shrink-0 text-amber-600" />
          <div className="flex-1">
            <div className="font-medium">Knowledge base is empty</div>
            <div className="text-xs text-muted-foreground">Refresh AWS data to start chatting.</div>
          </div>
          <Button asChild size="sm" variant="outline">
            <Link to="/knowledge">Set up</Link>
          </Button>
        </div>
      )}
      <div className="mt-8 grid w-full gap-3 sm:grid-cols-2">
        {EXAMPLES.map(({ icon: Icon, title, hint }) => (
          <button
            key={title}
            disabled={!kbReady}
            onClick={() => onPick(title)}
            className="group flex items-start gap-3 rounded-xl border bg-card p-4 text-left transition hover:border-primary/40 hover:shadow-sm disabled:cursor-not-allowed disabled:opacity-50"
          >
            <span className="rounded-lg bg-primary/10 p-2 text-primary">
              <Icon className="h-4 w-4" />
            </span>
            <span>
              <span className="block text-sm font-medium">{title}</span>
              <span className="block text-xs text-muted-foreground">{hint}</span>
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}
