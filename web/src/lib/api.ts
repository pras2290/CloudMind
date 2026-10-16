export type Session = { session_id: string; title: string; last_active: string | null };

export type SourceDoc = { source: string; type: string | null; title: string | null; snippet: string };

export type Message = {
  role: "user" | "assistant";
  content: string;
  timestamp: string | null;
  source: string | null;
  confidence: number | null;
  docs?: SourceDoc[];
};

export type Job = {
  id: string;
  status: "running" | "succeeded" | "failed";
  error: string | null;
  started_at: string;
  finished_at: string | null;
};

export type KBStatus = {
  ready: boolean;
  total: number;
  by_source: Record<string, number>;
  last_refreshed: string | null;
  job: Job | null;
};

export type UploadedFile = { name: string; size: number; modified: string };

export type ChatResponse = {
  session_id: string;
  answer: string;
  source: string;
  confidence: number;
  docs: SourceDoc[];
};

export const GENERIC_ERROR = "Something went wrong, please try again.";

export class ApiError extends Error {
  constructor(message: string, readonly status: number) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`/api${path}`, init);
  } catch {
    throw new ApiError("Can't reach the CloudMind server. Check your connection and try again.", 0);
  }
  if (!res.ok) {
    let detail = GENERIC_ERROR;
    try {
      const body = await res.json();
      if (typeof body.detail === "string") detail = body.detail;
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(detail, res.status);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

const json = (body: unknown): RequestInit => ({
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export const api = {
  kbStatus: () => request<KBStatus>("/kb/status"),
  refresh: () => request<Job>("/kb/refresh", { method: "POST" }),
  job: (id: string) => request<Job>(`/kb/jobs/${id}`),
  uploads: () => request<UploadedFile[]>("/uploads"),
  upload: (file: File) => {
    const form = new FormData();
    form.append("files", file);
    return request<UploadedFile[]>("/uploads", { method: "POST", body: form });
  },
  sessions: () => request<Session[]>("/sessions"),
  messages: (id: string) => request<Message[]>(`/sessions/${encodeURIComponent(id)}/messages`),
  deleteSession: (id: string) => request<void>(`/sessions/${encodeURIComponent(id)}`, { method: "DELETE" }),
  chat: (message: string, sessionId: string) => request<ChatResponse>("/chat", json({ message, session_id: sessionId })),
};
