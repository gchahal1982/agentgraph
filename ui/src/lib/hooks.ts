"use client";

import useSWR from "swr";

const fetcher = (url: string) => fetch(url).then((r) => r.json());

export function useAgents() {
  return useSWR<{ agents: Agent[] }>("/api/agents", fetcher, { refreshInterval: 5000 });
}

export function useThreads() {
  return useSWR<{ threads: string[] }>("/api/threads", fetcher, { refreshInterval: 5000 });
}

export function useAudit(limit = 50, runId?: string) {
  const params = new URLSearchParams();
  params.set("limit", String(limit));
  if (runId) params.set("run_id", runId);
  return useSWR<{ events: AuditEvent[] }>(`/api/audit?${params}`, fetcher, { refreshInterval: 2000 });
}

export type Agent = {
  name: string;
  description: string;
  vertical: string;
  metadata: Record<string, unknown>;
};

export type AuditEvent = {
  id: string;
  ts: number;
  run_id: string;
  thread_id: string;
  principal_id: string | null;
  action: string;
  actor: string;
  payload: Record<string, unknown>;
};
