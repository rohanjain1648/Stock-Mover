import type { Group, Summary } from "@/types/run";
import { Progress } from "@/components/ui/progress";
import { inr, num } from "@/lib/format";

function Kpi({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="min-w-0 rounded-lg border bg-card px-3.5 py-3">
      <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{label}</div>
      <div className="tnum mt-1 font-display text-2xl font-semibold leading-tight">{value}</div>
      {sub && <div className="mt-0.5 truncate text-xs text-muted-foreground">{sub}</div>}
    </div>
  );
}

export function KpiStrip({ summary, groups }: { summary: Summary; groups: Group[] }) {
  const s = summary ?? ({} as Summary);
  const total = groups.length;
  const approved = groups.filter((g) => g.decision === "approve").length;
  const rejected = groups.filter((g) => g.decision === "reject").length;
  const decided = approved + rejected;
  const deferred = s.deferred;

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-3 lg:grid-cols-5">
        <Kpi label="Moves" value={num(s.n_groups ?? total)} sub={`${num(s.n_moves)} SKU lines`} />
        <Kpi label="Units" value={num(s.units)} sub={`${num(s.stores_touched)} stores touched`} />
        <Kpi label="Value at MRP" value={inr(s.mrp_value)} />
        <Kpi label="Revenue protected" value={inr(s.revenue_protected)} sub="sales a store would miss" />
        <Kpi label="Need sign-off" value={num(s.needs_approval)} sub="moves over ₹1 L" />
      </div>
      <div className="flex flex-col gap-1.5 sm:flex-row sm:items-center sm:gap-4">
        <div className="flex-1">
          <Progress value={total ? (decided / total) * 100 : 0} className="h-2 bg-secondary" aria-label="Decisions made" />
        </div>
        <p className="tnum text-sm text-muted-foreground">
          <span className="font-semibold text-foreground">
            {num(decided)} of {num(total)} decided
          </span>
          {decided > 0 && ` · ${num(approved)} approved · ${num(rejected)} rejected`}
          {deferred && deferred.groups > 0 && ` · ${num(deferred.groups)} small moves deferred to tomorrow`}
        </p>
      </div>
    </div>
  );
}
