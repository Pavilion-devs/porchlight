import type { Baseline, DailySummary, LiveView, PorchEvent, Source, Status } from "../../shared/types";

// Same origin in production (the backend serves this app); proxied to :8000 by Vite in dev.
const BASE = import.meta.env.VITE_API_URL ?? "";

async function get<T>(path: string): Promise<T> {
  const r = await fetch(BASE + path);
  if (!r.ok) throw new Error(`${path}: ${r.status}`);
  return r.json();
}

export const api = {
  events: () => get<PorchEvent[]>("/api/events?limit=1000"),
  live: () => get<LiveView>("/api/live"),
  status: () => get<Status>("/api/status"),
  summary: (source: Source) => get<DailySummary>(`/api/summary/today?source=${source}`),
  baseline: (source: Source) => get<Baseline>(`/api/baseline?source=${source}`),
  startDemo: async (scenario: string) => {
    const r = await fetch(`${BASE}/api/demo/${scenario}`, { method: "POST" });
    if (!r.ok) throw new Error((await r.json().catch(() => null))?.detail ?? `HTTP ${r.status}`);
  },
};

export const frameUrl = (path?: string | null) => (path ? BASE + path : null);

export function wsUrl(): string {
  if (BASE) return BASE.replace(/^http/, "ws") + "/ws";
  return `${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws`;
}
