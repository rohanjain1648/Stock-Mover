import type { NotificationLogItem, Run, RunListItem, StoreRow } from "@/types/run";

export type Source = "live" | "snapshot";
export type DecisionValue = "approve" | "reject";

/** Base URL of the S4 API, no trailing slash. Empty → same origin (still tried, then snapshot). */
export function apiBase(): string {
  return (import.meta.env.VITE_API_URL ?? "").trim().replace(/\/+$/, "");
}

export const LIVE_TIMEOUT_MS = 5000;
const SNAPSHOT_URL = "/sample_run.json";

async function getJson<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText || "request failed"}`.trim());
  const text = await res.text();
  try {
    return JSON.parse(text) as T;
  } catch {
    // e.g. the SPA host answering /api/* with index.html
    throw new Error("API answered with something that is not JSON");
  }
}

function withTimeout(ms: number): { signal: AbortSignal; done: () => void } {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), ms);
  return { signal: ctrl.signal, done: () => clearTimeout(t) };
}

/** Latest run from the API; if it does not answer in 5 s, the bundled snapshot. */
export async function fetchLatest(): Promise<{ run: Run; source: Source }> {
  const { signal, done } = withTimeout(LIVE_TIMEOUT_MS);
  try {
    const run = await getJson<Run>(`${apiBase()}/api/runs/latest`, { signal, headers: { Accept: "application/json" } });
    if (!run || typeof run !== "object" || !("run_id" in run)) throw new Error("not a run");
    return { run, source: "live" };
  } catch {
    const run = await getJson<Run>(SNAPSHOT_URL);
    return { run, source: "snapshot" };
  } finally {
    done();
  }
}

function postJson<T>(path: string, body: unknown): Promise<T> {
  return getJson<T>(`${apiBase()}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify(body),
  });
}

export async function decide(groupId: string, decision: DecisionValue, note?: string): Promise<void> {
  const body: Record<string, unknown> = { decision };
  if (note) body.note = note;
  await postJson(`/api/groups/${encodeURIComponent(groupId)}/decision`, body);
}

export async function decideMany(groupIds: string[], decision: DecisionValue, note?: string): Promise<number> {
  const body: Record<string, unknown> = { group_ids: groupIds, decision };
  if (note) body.note = note;
  const r = await postJson<{ updated: number }>(`/api/groups/decision`, body);
  return typeof r?.updated === "number" ? r.updated : 0;
}

export function fetchRuns(): Promise<RunListItem[]> {
  return getJson<RunListItem[]>(`${apiBase()}/api/runs`);
}

export function fetchStores(): Promise<StoreRow[]> {
  return getJson<StoreRow[]>(`${apiBase()}/api/stores`);
}

export function fetchNotificationLog(): Promise<NotificationLogItem[]> {
  return getJson<NotificationLogItem[]>(`${apiBase()}/api/notifications/log`);
}

export function exportUrl(status: "approved" | "rejected" | "all" = "approved"): string {
  return `${apiBase()}/api/export.csv?status=${status}`;
}
