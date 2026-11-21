import { useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowDownLeft, ArrowUpRight, Warehouse } from "lucide-react";
import type { Group, StorePos } from "@/types/run";
import { RunHeader } from "@/components/RunHeader";
import { PageError, PageLoading } from "@/components/PageState";
import { useRun } from "@/lib/useRun";
import { amForStore, WAREHOUSE_ID } from "@/lib/areaManagers";
import { days, num, pct, perDay } from "@/lib/format";
import { cn } from "@/lib/utils";

type Flow = { inbound: number; outbound: number; moves: number };

function flows(groups: Group[]): Record<string, Flow> {
  const f: Record<string, Flow> = {};
  const at = (id: string) => (f[id] ??= { inbound: 0, outbound: 0, moves: 0 });
  for (const g of groups) {
    at(g.to).inbound += g.qty || 0;
    at(g.to).moves += 1;
    at(g.from).outbound += g.qty || 0;
    at(g.from).moves += 1;
  }
  return f;
}

function utilTone(u: number) {
  if (u > 1) return { bar: "bg-maroon", text: "text-maroon", note: "Over capacity" };
  if (u < 0.5) return { bar: "bg-amber-500", text: "text-amber-700", note: "Under half full" };
  return { bar: "bg-ok", text: "text-ok", note: "" };
}

function FlowLine({ flow }: { flow?: Flow }) {
  return (
    <div className="tnum flex items-center gap-3 text-xs text-muted-foreground">
      <span className="inline-flex items-center gap-1">
        <ArrowDownLeft className="h-3.5 w-3.5 text-ok" aria-hidden />
        {num(flow?.inbound ?? 0)} in
      </span>
      <span className="inline-flex items-center gap-1">
        <ArrowUpRight className="h-3.5 w-3.5 text-saffron" aria-hidden />
        {num(flow?.outbound ?? 0)} out
      </span>
      <span>· {num(flow?.moves ?? 0)} moves</span>
    </div>
  );
}

function StoreCard({ s, flow, onOpen }: { s: StorePos; flow?: Flow; onOpen: () => void }) {
  const u = s.utilisation ?? (s.capacity ? s.units / s.capacity : 0);
  const tone = utilTone(u);
  const am = amForStore(s.store_id);
  return (
    <button
      type="button"
      onClick={onOpen}
      className="group flex w-full flex-col gap-2.5 rounded-xl border bg-card p-4 text-left shadow-sm transition hover:border-saffron/60 hover:shadow focus:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      aria-label={`Show moves for ${s.store_id}`}
    >
      <div className="flex items-start justify-between gap-2">
        <div>
          <h3 className="font-sans text-base font-semibold">{s.store_id}</h3>
          {am && <div className="text-xs text-muted-foreground">AM {am.name}</div>}
        </div>
        <span className="rounded-full border px-2 py-0.5 text-[11px] font-semibold">Tier {s.tier}</span>
      </div>
      <div>
        <div className="mb-1 flex items-baseline justify-between text-xs">
          <span className="tnum text-muted-foreground">
            {num(s.units)} / {num(s.capacity)} units
          </span>
          <span className={cn("tnum font-semibold", tone.text)}>{pct(u)}</span>
        </div>
        <div className="h-2 overflow-hidden rounded-full bg-secondary" role="presentation">
          <div className={cn("h-full rounded-full", tone.bar)} style={{ width: `${Math.min(100, Math.max(2, u * 100))}%` }} />
        </div>
        {tone.note && <div className={cn("mt-1 text-[11px] font-medium", tone.text)}>{tone.note}</div>}
      </div>
      <div className="tnum flex flex-wrap gap-x-3 text-xs text-muted-foreground">
        <span>
          Cover <span className="font-medium text-foreground">{days(s.cover_days)}</span>
        </span>
        <span>
          Sells <span className="font-medium text-foreground">{perDay(s.vel_daily)}</span>
        </span>
      </div>
      {s.below_min?.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {s.below_min.map((c) => (
            <span key={c} className="rounded bg-saffron/10 px-1.5 py-0.5 text-[11px] font-medium text-saffron">
              Below min · {c}
            </span>
          ))}
        </div>
      )}
      <FlowLine flow={flow} />
    </button>
  );
}

export default function Stores() {
  const q = useRun();
  const navigate = useNavigate();
  const run = q.data?.run;

  const view = useMemo(() => {
    if (!run) return null;
    const f = flows(run.groups ?? []);
    const byCity = new Map<string, StorePos[]>();
    for (const s of run.stores ?? []) {
      if (!byCity.has(s.city)) byCity.set(s.city, []);
      byCity.get(s.city)!.push(s);
    }
    return { f, cities: Array.from(byCity.entries()) };
  }, [run]);

  if (q.isLoading) return <PageLoading />;
  if (!run || !view) return <PageError onRetry={() => q.refetch()} />;

  const open = (id: string) => navigate(`/?store=${encodeURIComponent(id)}`);
  const wh = view.f[WAREHOUSE_ID];

  return (
    <div className="space-y-6">
      <RunHeader showExport={false} />
      <div>
        <h1 className="text-2xl font-semibold sm:text-3xl">Stores</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Fill against capacity, days of cover and today's moves in and out. Tap a store to see its moves.
        </p>
      </div>

      <section aria-label="Warehouse">
        <button
          type="button"
          onClick={() => open(WAREHOUSE_ID)}
          className="flex w-full flex-col gap-2 rounded-xl border border-saffron/40 bg-saffron/[0.06] p-4 text-left shadow-sm transition hover:border-saffron focus:outline-none focus-visible:ring-2 focus-visible:ring-ring sm:flex-row sm:items-center sm:justify-between"
          aria-label={`Show moves for ${WAREHOUSE_ID}`}
        >
          <div className="flex items-center gap-3">
            <span className="grid h-10 w-10 place-items-center rounded-lg bg-saffron text-cream">
              <Warehouse className="h-5 w-5" aria-hidden />
            </span>
            <div>
              <h3 className="font-sans text-base font-semibold">{WAREHOUSE_ID}</h3>
              <div className="text-xs text-muted-foreground">Kolkata warehouse · sends to stores, takes pull-backs</div>
            </div>
          </div>
          <div className="tnum flex gap-4 text-sm">
            <span>
              <span className="font-semibold">{num(wh?.outbound ?? 0)}</span> units out
            </span>
            <span>
              <span className="font-semibold">{num(wh?.inbound ?? 0)}</span> pulled back
            </span>
          </div>
        </button>
      </section>

      {view.cities.map(([city, stores]) => (
        <section key={city} aria-labelledby={`city-${city}`} className="space-y-2.5">
          <h2 id={`city-${city}`} className="text-lg font-semibold">
            {city}
          </h2>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {stores.map((s) => (
              <StoreCard key={s.store_id} s={s} flow={view.f[s.store_id]} onOpen={() => open(s.store_id)} />
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}
