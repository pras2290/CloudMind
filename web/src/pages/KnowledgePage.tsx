import { useCallback, useEffect, useRef, useState, type DragEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Activity, CheckCircle2, Clock, Cloud, DollarSign, FileText, FileUp, HardDrive, Layers, Loader2, RefreshCw,
  Server, ShieldCheck, UploadCloud, XCircle, Zap,
} from "lucide-react";
import { toast } from "sonner";
import { api, type Job } from "@/lib/api";
import { keys, useKBStatus } from "@/lib/queries";
import { cn, formatBytes, relativeTime } from "@/lib/utils";
import { Button } from "@/components/ui/button";

const SOURCE_CARDS = [
  { key: "aws_ec2", label: "EC2", desc: "Instances, security groups, VPCs", icon: Server },
  { key: "aws_s3", label: "S3", desc: "Buckets and configuration", icon: HardDrive },
  { key: "aws_lambda", label: "Lambda", desc: "Functions and runtimes", icon: Zap },
  { key: "aws_cloudwatch", label: "CloudWatch", desc: "Alarms and log groups", icon: Activity },
  { key: "aws_iam", label: "IAM", desc: "Users, roles, MFA status", icon: ShieldCheck },
  { key: "aws_cost_explorer", label: "Cost Explorer", desc: "Spend by service, forecast", icon: DollarSign },
  { key: "uploads", label: "Uploaded docs", desc: "Runbooks, KEDB, SOPs", icon: FileText },
];

const ACCEPT = [".pdf", ".docx", ".csv", ".txt"];
const MAX_BYTES = 25 * 1024 * 1024;

type UploadItem = { id: string; name: string; size: number; status: "uploading" | "done" | "error"; error?: string };

export default function KnowledgePage() {
  const queryClient = useQueryClient();
  const { data: kb, isLoading } = useKBStatus();
  const uploads = useQuery({ queryKey: keys.uploads, queryFn: api.uploads });
  const [jobId, setJobId] = useState<string | null>(null);
  const [items, setItems] = useState<UploadItem[]>([]);
  const [dragging, setDragging] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);

  const activeJobId = jobId ?? kb?.job?.id ?? null;
  const job = useQuery({
    queryKey: ["job", activeJobId],
    queryFn: () => api.job(activeJobId!),
    enabled: !!activeJobId,
    refetchInterval: (q) => (q.state.data?.status === "running" || !q.state.data ? 1500 : false),
  });
  const running = job.data?.status === "running" || !!kb?.job;

  const finished = useRef<string | null>(null);
  useEffect(() => {
    const j: Job | undefined = job.data;
    if (!j || j.status === "running" || finished.current === j.id) return;
    finished.current = j.id;
    queryClient.invalidateQueries({ queryKey: keys.kb });
    if (j.status === "succeeded") toast.success("Knowledge base updated");
    else toast.error(j.error ?? "Refresh failed");
    setJobId(null);
  }, [job.data, queryClient]);

  const refresh = useMutation({
    mutationFn: api.refresh,
    onSuccess: (j) => {
      setJobId(j.id);
      queryClient.invalidateQueries({ queryKey: keys.kb });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const addFiles = useCallback(
    async (files: File[]) => {
      for (const file of files) {
        const id = `${file.name}-${Date.now()}-${Math.random()}`;
        const ext = file.name.slice(file.name.lastIndexOf(".")).toLowerCase();
        const base: UploadItem = { id, name: file.name, size: file.size, status: "uploading" };
        if (!ACCEPT.includes(ext)) {
          setItems((p) => [{ ...base, status: "error", error: "Unsupported file type" }, ...p]);
          continue;
        }
        if (file.size > MAX_BYTES) {
          setItems((p) => [{ ...base, status: "error", error: "Larger than 25 MB" }, ...p]);
          continue;
        }
        setItems((p) => [base, ...p]);
        try {
          const [saved] = await api.upload(file);
          setItems((p) => p.map((it) => (it.id === id ? { ...it, name: saved.name, status: "done" } : it)));
        } catch (e) {
          setItems((p) => p.map((it) => (it.id === id ? { ...it, status: "error", error: (e as Error).message } : it)));
        }
      }
      queryClient.invalidateQueries({ queryKey: keys.uploads });
    },
    [queryClient],
  );

  const onDrop = (e: DragEvent) => {
    e.preventDefault();
    setDragging(false);
    addFiles(Array.from(e.dataTransfer.files));
  };

  const status = running ? "Indexing" : kb?.ready ? "Ready" : "Empty";

  return (
    <div className="scrollbar-thin h-full overflow-y-auto">
      <div className="mx-auto max-w-5xl space-y-8 px-4 py-8 md:px-8">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <h2 className="text-2xl font-semibold tracking-tight">Knowledge base</h2>
            <p className="mt-1 text-sm text-muted-foreground">AWS resources and documents CloudMind searches to answer your questions.</p>
          </div>
          <Button onClick={() => refresh.mutate()} disabled={running || refresh.isPending}>
            {running ? <Loader2 className="animate-spin" /> : <RefreshCw />}
            {running ? "Refreshing…" : "Refresh AWS data"}
          </Button>
        </div>

        {running && (
          <div className="overflow-hidden rounded-lg border bg-card" role="status">
            <div className="flex items-center gap-3 p-4 text-sm">
              <Loader2 className="h-4 w-4 animate-spin text-primary" />
              <div className="flex-1">
                <div className="font-medium">Refreshing knowledge base</div>
                <div className="text-xs text-muted-foreground">Fetching AWS services and indexing uploaded documents. You can keep chatting meanwhile.</div>
              </div>
            </div>
            <div className="h-1 w-full bg-muted">
              <div className="h-1 w-1/3 animate-progress bg-primary" />
            </div>
          </div>
        )}

        <div className="grid gap-4 sm:grid-cols-3">
          <StatCard icon={Layers} label="Indexed chunks" value={isLoading ? "—" : (kb?.total ?? 0).toLocaleString()} />
          <StatCard
            icon={status === "Ready" ? CheckCircle2 : status === "Indexing" ? Loader2 : Cloud}
            label="Status"
            value={isLoading ? "—" : status}
            tone={status === "Ready" ? "text-emerald-600" : status === "Indexing" ? "text-primary" : "text-amber-600"}
            spin={status === "Indexing"}
          />
          <StatCard icon={Clock} label="Last refreshed" value={isLoading ? "—" : relativeTime(kb?.last_refreshed)} />
        </div>

        <section>
          <h3 className="mb-3 text-sm font-semibold">Sources</h3>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {SOURCE_CARDS.map(({ key, label, desc, icon: Icon }) => {
              const count = kb?.by_source[key] ?? 0;
              return (
                <div key={key} className="rounded-xl border bg-card p-4">
                  <div className="flex items-center justify-between">
                    <span className="rounded-lg bg-primary/10 p-2 text-primary">
                      <Icon className="h-4 w-4" />
                    </span>
                    <span className={cn("text-xl font-semibold tabular-nums", count === 0 && "text-muted-foreground")}>{count}</span>
                  </div>
                  <div className="mt-3 text-sm font-medium">{label}</div>
                  <div className="text-xs text-muted-foreground">{desc}</div>
                </div>
              );
            })}
          </div>
        </section>

        <section className="grid gap-6 lg:grid-cols-5">
          <div className="lg:col-span-3">
            <div className="mb-3 flex items-center justify-between">
              <h3 className="text-sm font-semibold">Upload documents</h3>
            </div>
            <div
              role="button"
              tabIndex={0}
              onClick={() => fileInput.current?.click()}
              onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && fileInput.current?.click()}
              onDragOver={(e) => {
                e.preventDefault();
                setDragging(true);
              }}
              onDragLeave={() => setDragging(false)}
              onDrop={onDrop}
              className={cn(
                "flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed p-8 text-center transition",
                dragging ? "border-primary bg-primary/5" : "hover:border-primary/40 hover:bg-muted/40",
              )}
            >
              <UploadCloud className="h-8 w-8 text-muted-foreground" />
              <div className="mt-3 text-sm font-medium">Drop files here or click to browse</div>
              <div className="mt-1 text-xs text-muted-foreground">PDF, DOCX, CSV or TXT · up to 25 MB each</div>
              <input
                ref={fileInput}
                type="file"
                multiple
                accept={ACCEPT.join(",")}
                className="hidden"
                data-testid="file-input"
                onChange={(e) => {
                  addFiles(Array.from(e.target.files ?? []));
                  e.target.value = "";
                }}
              />
            </div>
            {items.length > 0 && (
              <ul className="mt-3 space-y-2">
                {items.map((it) => (
                  <li key={it.id} className="flex items-center gap-3 rounded-lg border bg-card px-3 py-2 text-sm">
                    <FileUp className="h-4 w-4 shrink-0 text-muted-foreground" />
                    <span className="min-w-0 flex-1 truncate">{it.name}</span>
                    <span className="text-xs text-muted-foreground">{formatBytes(it.size)}</span>
                    {it.status === "uploading" && <Loader2 className="h-4 w-4 animate-spin text-primary" aria-label="Uploading" />}
                    {it.status === "done" && <CheckCircle2 className="h-4 w-4 text-emerald-500" aria-label="Uploaded" />}
                    {it.status === "error" && (
                      <span className="flex items-center gap-1 text-xs text-rose-600">
                        <XCircle className="h-4 w-4" /> {it.error}
                      </span>
                    )}
                  </li>
                ))}
              </ul>
            )}
            {items.some((i) => i.status === "done") && (
              <div className="mt-3 flex items-center justify-between rounded-lg bg-primary/5 px-3 py-2 text-sm">
                <span className="text-muted-foreground">New files are searchable after indexing.</span>
                <Button size="sm" onClick={() => refresh.mutate()} disabled={running}>
                  Index uploaded files
                </Button>
              </div>
            )}
          </div>

          <div className="lg:col-span-2">
            <h3 className="mb-3 text-sm font-semibold">Uploaded files</h3>
            <div className="overflow-hidden rounded-xl border bg-card">
              {uploads.isLoading ? (
                <div className="p-4 text-sm text-muted-foreground">Loading…</div>
              ) : uploads.data?.length ? (
                <ul className="divide-y text-sm">
                  {uploads.data.map((f) => (
                    <li key={f.name} className="flex items-center gap-3 px-4 py-2.5">
                      <FileText className="h-4 w-4 shrink-0 text-muted-foreground" />
                      <span className="min-w-0 flex-1 truncate">{f.name}</span>
                      <span className="text-xs text-muted-foreground">{formatBytes(f.size)}</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <div className="p-6 text-center text-sm text-muted-foreground">No documents uploaded yet</div>
              )}
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}

function StatCard({ icon: Icon, label, value, tone, spin }: { icon: typeof Layers; label: string; value: string; tone?: string; spin?: boolean }) {
  return (
    <div className="rounded-xl border bg-card p-5">
      <div className="flex items-center gap-2 text-xs font-medium text-muted-foreground">
        <Icon className={cn("h-4 w-4", tone, spin && "animate-spin")} /> {label}
      </div>
      <div className={cn("mt-2 text-2xl font-semibold tracking-tight", tone)}>{value}</div>
    </div>
  );
}
