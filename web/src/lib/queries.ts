import { useQuery } from "@tanstack/react-query";
import { api } from "./api";

export const keys = {
  kb: ["kb-status"] as const,
  sessions: ["sessions"] as const,
  messages: (id: string) => ["messages", id] as const,
  uploads: ["uploads"] as const,
};

export function useKBStatus() {
  return useQuery({
    queryKey: keys.kb,
    queryFn: api.kbStatus,
    refetchInterval: (q) => (q.state.data?.job ? 2000 : 30000),
  });
}

export function useSessions() {
  return useQuery({ queryKey: keys.sessions, queryFn: api.sessions });
}
