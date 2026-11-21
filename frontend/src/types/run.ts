// Mirrors contracts/CONTRACTS.md C2 (run JSON) and C3 (REST responses). snake_case on purpose.

export type MoveType = "WH_TO_STORE" | "STORE_TO_STORE" | "PULL_BACK";

export type ProblemKind =
  | "CAPACITY"
  | "OVERSTOCK"
  | "UNDERSTOCK"
  | "SCARCITY"
  | "NEW_LAUNCH"
  | "MIN_DISPLAY"
  | "AGEING"
  | "SOLD_OUT_CONSOLIDATION";

export type FlagKind = "DATA_QUALITY" | "REORDER" | "DEAD_STOCK" | "NEW_STORE" | "CAPACITY";

export type Decision = "approve" | "reject" | null;

export interface Summary {
  n_groups: number;
  n_moves: number;
  units: number;
  mrp_value: number;
  revenue_protected: number;
  needs_approval: number;
  by_type: Partial<Record<MoveType, number>>;
  stores_touched: number;
  deferred?: { groups: number; units: number; revenue_at_risk: number };
}

export interface Problem {
  problem_id: string;
  kind: ProblemKind | string;
  title: string;
  detail: string;
  group_ids: string[];
}

export interface Evidence {
  from_cover_before: number | null;
  from_cover_after: number | null;
  to_cover_before: number | null;
  to_cover_after: number | null;
  to_vel_daily: number | null;
  from_vel_daily: number | null;
  lift: number | null;
  age_days: number | null;
  to_capacity_after: number | null;
}

export interface Line {
  sku_id: string;
  size: string;
  qty: number;
}

export interface Group {
  group_id: string;
  type: MoveType;
  problem_kind: ProblemKind | string;
  style_id: string;
  style_name: string;
  category: string;
  from: string;
  to: string;
  ship_on: string;
  arrives_on: string;
  lead_days: number;
  sizes: Record<string, number>;
  qty: number;
  mrp_value: number;
  revenue_at_risk: number;
  priority: number;
  needs_approval: boolean;
  explanation: string;
  evidence: Partial<Evidence> | null;
  lines: Line[];
  /** Added by the API (C3 GET /api/runs/latest); absent in a bare snapshot. */
  decision?: Decision;
  decision_note?: string | null;
}

export interface Flag {
  flag_id: string;
  kind: FlagKind | string;
  location_id?: string | null;
  sku_id?: string | null;
  style_id?: string | null;
  message: string;
}

export interface StorePos {
  store_id: string;
  tier: string;
  city: string;
  zone: string;
  capacity: number;
  units: number;
  utilisation: number;
  vel_daily: number;
  cover_days: number | null;
  below_min: string[];
}

/** GET /api/stores row. */
export interface StoreRow extends StorePos {
  inbound_units: number;
  outbound_units: number;
  group_ids: string[];
}

export interface Violation {
  rule: string;
  group_id: string;
  detail: string;
}

export interface Validation {
  passed: boolean;
  checked_moves: number;
  violations: Violation[];
}

export interface Run {
  run_id: string;
  as_of: string;
  generated_at: string;
  trigger: string;
  summary: Summary;
  problems: Problem[];
  groups: Group[];
  flags: Flag[];
  stores: StorePos[];
  validation: Validation;
}

export interface RunListItem {
  run_id: string;
  generated_at: string;
  trigger: string;
  n_groups: number;
  passed: boolean;
}

export interface NotificationLogItem {
  sent_at: string;
  channel: "email" | "fo" | string;
  to: string;
  subject: string;
  ok: boolean;
}
