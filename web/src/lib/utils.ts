import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export type SourceMeta = { label: string; className: string };

const SOURCES: Record<string, SourceMeta> = {
  aws_ec2: { label: "EC2", className: "bg-orange-500/10 text-orange-700 dark:text-orange-300 ring-orange-500/20" },
  aws_s3: { label: "S3", className: "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 ring-emerald-500/20" },
  aws_lambda: { label: "Lambda", className: "bg-amber-500/10 text-amber-700 dark:text-amber-300 ring-amber-500/20" },
  aws_cloudwatch: { label: "CloudWatch", className: "bg-pink-500/10 text-pink-700 dark:text-pink-300 ring-pink-500/20" },
  aws_iam: { label: "IAM", className: "bg-rose-500/10 text-rose-700 dark:text-rose-300 ring-rose-500/20" },
  aws_cost_explorer: { label: "Cost Explorer", className: "bg-sky-500/10 text-sky-700 dark:text-sky-300 ring-sky-500/20" },
  uploads: { label: "Uploaded docs", className: "bg-violet-500/10 text-violet-700 dark:text-violet-300 ring-violet-500/20" },
  live_aws_ec2: { label: "Live EC2", className: "bg-green-500/10 text-green-700 dark:text-green-300 ring-green-500/20" },
  live_aws_cost: { label: "Live cost", className: "bg-green-500/10 text-green-700 dark:text-green-300 ring-green-500/20" },
  system: { label: "CloudMind", className: "bg-indigo-500/10 text-indigo-700 dark:text-indigo-300 ring-indigo-500/20" },
  knowledge_base: { label: "Knowledge base", className: "bg-indigo-500/10 text-indigo-700 dark:text-indigo-300 ring-indigo-500/20" },
  none: { label: "No match", className: "bg-slate-500/10 text-slate-700 dark:text-slate-300 ring-slate-500/20" },
  live_aws: { label: "Live AWS", className: "bg-green-500/10 text-green-700 dark:text-green-300 ring-green-500/20" },
  general: { label: "General", className: "bg-slate-500/10 text-slate-700 dark:text-slate-300 ring-slate-500/20" },
  all: { label: "Knowledge base", className: "bg-indigo-500/10 text-indigo-700 dark:text-indigo-300 ring-indigo-500/20" },
  hybrid: { label: "Knowledge base", className: "bg-indigo-500/10 text-indigo-700 dark:text-indigo-300 ring-indigo-500/20" },
};

export function sourceMeta(source: string | null | undefined): SourceMeta {
  if (!source) return SOURCES.general;
  if (SOURCES[source]) return SOURCES[source];
  const label = source.replace(/^aws_/, "").replace(/_/g, " ");
  return {
    label: label.charAt(0).toUpperCase() + label.slice(1),
    className: "bg-slate-500/10 text-slate-700 dark:text-slate-300 ring-slate-500/20",
  };
}

export type ConfidenceLevel = { label: "High" | "Medium" | "Low"; className: string };

export function confidenceLevel(value: number): ConfidenceLevel {
  if (value >= 0.7) return { label: "High", className: "bg-emerald-500" };
  if (value >= 0.4) return { label: "Medium", className: "bg-amber-500" };
  return { label: "Low", className: "bg-rose-500" };
}

/** SQLite CURRENT_TIMESTAMP values are UTC without a zone marker. */
export function parseTimestamp(ts: string | null | undefined): Date | null {
  if (!ts) return null;
  const iso = /[zZ]|[+-]\d\d:?\d\d$/.test(ts) ? ts : ts.replace(" ", "T") + "Z";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? null : d;
}

export type Group<T> = { label: string; items: T[] };

export function groupByRecency<T extends { last_active: string | null }>(items: T[], now = new Date()): Group<T>[] {
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  const day = 86_400_000;
  const buckets: Group<T>[] = [
    { label: "Today", items: [] },
    { label: "Yesterday", items: [] },
    { label: "Previous 7 days", items: [] },
    { label: "Older", items: [] },
  ];
  for (const item of items) {
    const t = parseTimestamp(item.last_active)?.getTime() ?? 0;
    if (t >= startOfToday) buckets[0].items.push(item);
    else if (t >= startOfToday - day) buckets[1].items.push(item);
    else if (t >= startOfToday - 7 * day) buckets[2].items.push(item);
    else buckets[3].items.push(item);
  }
  return buckets.filter((b) => b.items.length > 0);
}

export function relativeTime(ts: string | null | undefined, now = new Date()): string {
  const d = parseTimestamp(ts);
  if (!d) return "Never";
  const s = Math.round((now.getTime() - d.getTime()) / 1000);
  if (s < 60) return "Just now";
  if (s < 3600) return `${Math.floor(s / 60)} min ago`;
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`;
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function newId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) return crypto.randomUUID();
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    return (c === "x" ? r : (r & 0x3) | 0x8).toString(16);
  });
}
