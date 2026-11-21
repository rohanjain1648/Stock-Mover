import type { Group, Run } from "@/types/run";
import { amForStore, WAREHOUSE_ID } from "./areaManagers";

export const ALL = "all";

export interface FilterState {
  type: string;
  city: string;
  am: string;
  category: string;
  store: string;
  signoffOnly: boolean;
}

export const EMPTY_FILTERS: FilterState = { type: ALL, city: ALL, am: ALL, category: ALL, store: ALL, signoffOnly: false };

export function initialFilters(search: string = typeof window !== "undefined" ? window.location.search : ""): FilterState {
  const store = new URLSearchParams(search).get("store");
  return store ? { ...EMPTY_FILTERS, store } : EMPTY_FILTERS;
}

export function isFiltered(f: FilterState): boolean {
  return f.type !== ALL || f.city !== ALL || f.am !== ALL || f.category !== ALL || f.store !== ALL || f.signoffOnly;
}

/** store id → city, from the run's store positions; the warehouse is Kolkata. */
export function cityIndex(run: Run): Record<string, string> {
  const idx: Record<string, string> = { [WAREHOUSE_ID]: "Kolkata" };
  for (const s of run.stores ?? []) idx[s.store_id] = s.city;
  return idx;
}

/** A move matches a place filter when either end is in that place. */
export function matchesFilters(g: Group, f: FilterState, cities: Record<string, string>): boolean {
  if (f.type !== ALL && g.type !== f.type) return false;
  if (f.category !== ALL && g.category !== f.category) return false;
  if (f.signoffOnly && !g.needs_approval) return false;
  const ends = [g.from, g.to];
  if (f.store !== ALL && !ends.includes(f.store)) return false;
  if (f.city !== ALL && !ends.some((e) => cities[e] === f.city)) return false;
  if (f.am !== ALL && !ends.some((e) => amForStore(e)?.id === f.am)) return false;
  return true;
}
