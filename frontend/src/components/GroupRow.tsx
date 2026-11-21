import { useState } from "react";
import { ArrowRight, Check, ChevronDown, X } from "lucide-react";
import type { Group } from "@/types/run";
import { Button } from "@/components/ui/button";
import { Hint, LIVE_NEEDED } from "@/components/Hint";
import { coverEv, dash, inr, moveLabel, num, pct, perDay, shortDate } from "@/lib/format";
import type { DecisionValue } from "@/lib/api";
import { cn } from "@/lib/utils";

const TYPE_STYLE: Record<string, string> = {
  WH_TO_STORE: "bg-saffron/10 text-saffron",
  STORE_TO_STORE: "bg-ok/10 text-ok",
  PULL_BACK: "bg-maroon/10 text-maroon",
};

export function TypeChip({ type }: { type: string }) {
  return (
    <span className={cn("inline-flex shrink-0 items-center rounded px-1.5 py-0.5 text-[11px] font-semibold uppercase tracking-wide", TYPE_STYLE[type] ?? "bg-muted")}>
      {moveLabel(type)}
    </span>
  );
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0">
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="tnum text-sm font-medium">{value}</dd>
    </div>
  );
}

const arrow = (a: string, b: string) => (a === "—" && b === "—" ? "—" : `${a} → ${b}`);

function Details({ g }: { g: Group }) {
  const e = g.evidence ?? {};
  const lift = typeof e.lift === "number" && Number.isFinite(e.lift) ? `×${e.lift.toFixed(1)}` : "—";
  const age = typeof e.age_days === "number" && Number.isFinite(e.age_days) ? `${Math.round(e.age_days)} d` : "—";
  return (
    <div data-testid="group-details" className="mt-3 space-y-3 rounded-md border bg-background/60 p-3">
      <div className="flex flex-wrap items-center gap-1.5">
        {Object.entries(g.sizes ?? {}).map(([size, qty]) => (
          <span key={size} className="tnum rounded border bg-card px-2 py-0.5 text-xs">
            <span className="font-semibold">{size}</span> {num(qty)}
          </span>
        ))}
        <span className="ml-1 text-xs text-muted-foreground">
          Ships {shortDate(g.ship_on)} → arrives {shortDate(g.arrives_on)} ({dash(g.lead_days)} d lead time)
        </span>
      </div>
      <dl className="grid grid-cols-2 gap-x-4 gap-y-2 sm:grid-cols-4">
        <Fact label={`Cover at ${g.from}`} value={arrow(coverEv(e.from_cover_before), coverEv(e.from_cover_after))} />
        <Fact label={`Cover at ${g.to}`} value={arrow(coverEv(e.to_cover_before), coverEv(e.to_cover_after))} />
        <Fact label={`Sells at ${g.to}`} value={perDay(e.to_vel_daily)} />
        <Fact label={`Sells at ${g.from}`} value={perDay(e.from_vel_daily)} />
        <Fact label="Festive lift" value={lift} />
        <Fact label="Stock age" value={age} />
        <Fact label={`${g.to} fill after`} value={pct(e.to_capacity_after)} />
        <Fact label="Revenue at risk" value={inr(g.revenue_at_risk)} />
      </dl>
      {g.lines?.length > 0 && (
        <div className="text-xs">
          <div className="mb-1 text-muted-foreground">SKU lines</div>
          <ul className="flex flex-wrap gap-x-4 gap-y-1">
            {g.lines.map((l) => (
              <li key={l.sku_id} className="tnum">
                <span className="font-mono">{l.sku_id}</span> × {num(l.qty)}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

export function DecisionButtons({
  g,
  live,
  onDecide,
}: {
  g: Group;
  live: boolean;
  onDecide: (ids: string[], d: DecisionValue) => void;
}) {
  const hint = live ? null : LIVE_NEEDED;
  const approved = g.decision === "approve";
  const rejected = g.decision === "reject";
  return (
    <div className="flex shrink-0 items-center gap-1.5">
      <Hint text={hint} disabled={!live}>
        <Button
          size="sm"
          variant="outline"
          aria-label={`Approve ${g.group_id}`}
          aria-pressed={approved}
          disabled={!live}
          onClick={() => !approved && onDecide([g.group_id], "approve")}
          className={cn("h-8 px-2.5", approved && "border-ok bg-ok text-white hover:bg-ok/90 hover:text-white")}
        >
          <Check className="h-4 w-4" />
          <span className="ml-1 text-xs">{approved ? "Approved" : "Approve"}</span>
        </Button>
      </Hint>
      <Hint text={hint} disabled={!live}>
        <Button
          size="sm"
          variant="outline"
          aria-label={`Reject ${g.group_id}`}
          aria-pressed={rejected}
          disabled={!live}
          onClick={() => !rejected && onDecide([g.group_id], "reject")}
          className={cn("h-8 px-2", rejected && "border-maroon bg-maroon text-white hover:bg-maroon/90 hover:text-white")}
        >
          <X className="h-4 w-4" />
          {rejected && <span className="ml-1 text-xs">Rejected</span>}
        </Button>
      </Hint>
    </div>
  );
}

export function GroupRow({
  g,
  live,
  onDecide,
}: {
  g: Group;
  live: boolean;
  onDecide: (ids: string[], d: DecisionValue) => void;
}) {
  const [open, setOpen] = useState(false);
  return (
    <article
      className={cn(
        "border-t px-4 py-3 first:border-t-0",
        g.decision === "approve" && "bg-ok/[0.04]",
        g.decision === "reject" && "bg-maroon/[0.04] opacity-75",
      )}
    >
      <div className="flex flex-col gap-2.5 sm:flex-row sm:items-start sm:gap-4">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-sm">
            <TypeChip type={g.type} />
            <span className="inline-flex items-center gap-1 font-semibold">
              {g.from} <ArrowRight className="h-3.5 w-3.5 text-muted-foreground" aria-label="to" /> {g.to}
            </span>
            <span className="tnum">
              · {num(g.qty)} × <span className="font-medium">{g.style_id}</span>
            </span>
            <span className="min-w-0 truncate text-muted-foreground">{g.style_name}</span>
            {g.needs_approval && (
              <span className="rounded-full border border-saffron/50 bg-saffron/10 px-2 py-0.5 text-[11px] font-semibold text-saffron">
                Approval needed
              </span>
            )}
          </div>
          <p className="mt-1 text-sm leading-snug text-ink/80">{g.explanation}</p>
          <button
            type="button"
            onClick={() => setOpen((o) => !o)}
            aria-expanded={open}
            className="mt-1.5 inline-flex items-center gap-1 text-xs font-medium text-saffron hover:underline"
          >
            <ChevronDown className={cn("h-3.5 w-3.5 transition-transform", open && "rotate-180")} />
            {open ? "Hide details" : "Details"}
          </button>
        </div>
        <div className="flex items-center justify-between gap-3 sm:flex-col sm:items-end sm:justify-start">
          <div className="tnum text-left sm:text-right">
            <div className="text-sm font-semibold">{inr(g.mrp_value)}</div>
            <div className="text-[11px] text-muted-foreground">at MRP</div>
          </div>
          <DecisionButtons g={g} live={live} onDecide={onDecide} />
        </div>
      </div>
      {open && <Details g={g} />}
    </article>
  );
}
