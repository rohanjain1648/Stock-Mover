import type { MoveType } from "@/types/run";

const DASH = "—";

const isNum = (n: unknown): n is number => typeof n === "number" && Number.isFinite(n);

/** Indian digit grouping, rounded to a whole number. Missing → "—". */
export function num(n: number | null | undefined): string {
  if (!isNum(n)) return DASH;
  return Math.round(n).toLocaleString("en-IN");
}

/** Any value for display; null/undefined/NaN → "—". */
export function dash(v: unknown): string {
  if (v === null || v === undefined) return DASH;
  if (typeof v === "number" && !Number.isFinite(v)) return DASH;
  return String(v);
}

/** Money: ₹12,345 below a lakh, ₹2.5 L from a lakh, ₹3.1 Cr from a crore. */
export function inr(n: number | null | undefined): string {
  if (!isNum(n)) return DASH;
  const a = Math.abs(n);
  const sign = n < 0 ? "-" : "";
  if (a >= 1e7) return `${sign}₹${(a / 1e7).toFixed(1)} Cr`;
  if (a >= 1e5) return `${sign}₹${(a / 1e5).toFixed(1)} L`;
  return `${sign}₹${Math.round(a).toLocaleString("en-IN")}`;
}

/** Days of cover. null = infinite (no sales) → "∞". */
export function days(n: number | null | undefined): string {
  if (n === null) return "∞";
  if (!isNum(n)) return DASH;
  return `${Math.round(n)} d`;
}

/** Evidence cover value: null means "not applicable" here, so "—" (unlike days()). */
export function coverEv(n: number | null | undefined): string {
  if (!isNum(n)) return DASH;
  return `${Math.round(n)} d`;
}

export function pct(n: number | null | undefined, digits = 0): string {
  if (!isNum(n)) return DASH;
  return `${(n * 100).toFixed(digits)}%`;
}

export function perDay(n: number | null | undefined): string {
  if (!isNum(n)) return DASH;
  return `${n < 10 ? n.toFixed(2).replace(/\.?0+$/, "") || "0" : Math.round(n).toLocaleString("en-IN")}/day`;
}

const MOVE_LABELS: Record<MoveType, string> = {
  WH_TO_STORE: "Warehouse → store",
  STORE_TO_STORE: "Store → store",
  PULL_BACK: "Pull back",
};

export function moveLabel(t: MoveType | string): string {
  return MOVE_LABELS[t as MoveType] ?? String(t);
}

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** "2026-11-01" → "1 Nov". */
export function shortDate(iso: string | null | undefined): string {
  if (!iso) return DASH;
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso);
  if (!m) return iso;
  return `${Number(m[3])} ${MONTHS[Number(m[2]) - 1]}`;
}

/** "2026-10-31" → "31 Oct 2026". */
export function longDate(iso: string | null | undefined): string {
  if (!iso) return DASH;
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso);
  if (!m) return iso;
  return `${Number(m[3])} ${MONTHS[Number(m[2]) - 1]} ${m[1]}`;
}

/** ISO timestamp → "21 Nov, 13:41" in IST. */
export function istDateTime(iso: string | null | undefined): string {
  if (!iso) return DASH;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const parts = new Intl.DateTimeFormat("en-GB", {
    timeZone: "Asia/Kolkata",
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).formatToParts(d);
  const get = (t: string) => parts.find((p) => p.type === t)?.value ?? "";
  return `${get("day")} ${get("month")}, ${get("hour")}:${get("minute")}`;
}

/** ISO timestamp → "13:41" in IST. */
export function istTime(iso: string | null | undefined): string {
  if (!iso) return DASH;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return new Intl.DateTimeFormat("en-GB", {
    timeZone: "Asia/Kolkata",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(d);
}

export function triggerLabel(t: string | null | undefined): string {
  switch ((t ?? "").toLowerCase()) {
    case "schedule":
    case "scheduled":
      return "Scheduled 07:00";
    case "github":
      return "GitHub";
    case "manual":
      return "Manual";
    default:
      return t ? String(t) : DASH;
  }
}

export function plural(n: number, one: string, many = `${one}s`): string {
  return `${num(n)} ${n === 1 ? one : many}`;
}
