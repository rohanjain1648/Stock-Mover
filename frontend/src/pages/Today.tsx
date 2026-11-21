import { useMemo, useState } from "react";
import { PackageCheck } from "lucide-react";
import type { Group, Problem } from "@/types/run";
import { RunHeader } from "@/components/RunHeader";
import { KpiStrip } from "@/components/KpiStrip";
import { Filters } from "@/components/Filters";
import { ProblemCard } from "@/components/ProblemCard";
import { PageError, PageLoading } from "@/components/PageState";
import { Button } from "@/components/ui/button";
import { useDecide, useRun } from "@/lib/useRun";
import { cityIndex, EMPTY_FILTERS, initialFilters, isFiltered, matchesFilters, type FilterState } from "@/lib/filters";
import type { DecisionValue } from "@/lib/api";

const OPEN_BY_DEFAULT = 3;

/** Approval-needed moves pinned first, then by priority (₹ at risk / ₹ freed). */
const byPriority = (a: Group, b: Group) =>
  Number(b.needs_approval) - Number(a.needs_approval) || (b.priority ?? 0) - (a.priority ?? 0);

export default function Today() {
  const q = useRun();
  const decideM = useDecide();
  const [filters, setFiltersState] = useState<FilterState>(() => initialFilters());

  const setFilters = (f: FilterState) => {
    setFiltersState(f);
    // keep ?store= in the address bar in step with the store filter
    if (typeof window !== "undefined" && window.history?.replaceState) {
      const url = new URL(window.location.href);
      if (f.store && f.store !== EMPTY_FILTERS.store) url.searchParams.set("store", f.store);
      else url.searchParams.delete("store");
      window.history.replaceState(null, "", url.toString());
    }
  };

  const run = q.data?.run;
  const live = q.data?.source === "live";

  const view = useMemo(() => {
    if (!run) return null;
    const groups = run.groups ?? [];
    const byId = new Map(groups.map((g) => [g.group_id, g]));
    const cities = cityIndex(run);
    const cityList = Array.from(new Set((run.stores ?? []).map((s) => s.city))).sort();
    const claimed = new Set<string>();
    const cards: { problem: Problem; groups: Group[] }[] = [];
    for (const p of run.problems ?? []) {
      const gs = (p.group_ids ?? [])
        .map((id) => byId.get(id))
        .filter((g): g is Group => !!g);
      gs.forEach((g) => claimed.add(g.group_id));
      cards.push({ problem: p, groups: gs });
    }
    const orphans = groups.filter((g) => !claimed.has(g.group_id));
    if (orphans.length) {
      cards.push({
        problem: { problem_id: "P-OTHER-UI", kind: "OTHER", title: "Other moves", detail: "Moves not tied to a headline problem.", group_ids: orphans.map((g) => g.group_id) },
        groups: orphans,
      });
    }
    const shownCards = cards
      .map((c) => ({ ...c, groups: c.groups.filter((g) => matchesFilters(g, filters, cities)).sort(byPriority) }))
      .filter((c) => c.groups.length > 0);
    const shown = shownCards.reduce((a, c) => a + c.groups.length, 0);
    return { groups, cityList, shownCards, shown };
  }, [run, filters]);

  if (q.isLoading) return <PageLoading />;
  if (!run || !view) return <PageError onRetry={() => q.refetch()} />;

  const onDecide = (ids: string[], decision: DecisionValue) => {
    if (!live || ids.length === 0) return;
    decideM.mutate({ ids, decision });
  };

  const filtered = isFiltered(filters);

  return (
    <div className="space-y-5">
      <RunHeader />
      <div>
        <h1 className="text-2xl font-semibold sm:text-3xl">Today's moves</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Biggest problems first. Each move says why in one line; open Details for the numbers behind it.
        </p>
      </div>

      {view.groups.length === 0 ? (
        <div className="flex flex-col items-center gap-3 rounded-xl border border-dashed bg-card px-6 py-14 text-center">
          <PackageCheck className="h-10 w-10 text-ok" aria-hidden />
          <h2 className="text-xl font-semibold">No stock in the wrong place today</h2>
          <p className="max-w-md text-sm text-muted-foreground">
            Every store has the cover it needs and nothing is stuck. The next run checks again at 07:00 IST.
          </p>
        </div>
      ) : (
        <>
          <KpiStrip summary={run.summary} groups={view.groups} />
          <Filters value={filters} onChange={setFilters} groups={view.groups} cities={view.cityList} shown={view.shown} />
          {view.shownCards.length === 0 ? (
            <div className="rounded-xl border border-dashed bg-card px-6 py-10 text-center">
              <p className="font-medium">No moves match these filters.</p>
              <Button variant="link" onClick={() => setFilters(EMPTY_FILTERS)}>
                Clear filters
              </Button>
            </div>
          ) : (
            <div className="space-y-4">
              {view.shownCards.map((c, i) => (
                <ProblemCard
                  key={c.problem.problem_id}
                  problem={c.problem}
                  groups={c.groups}
                  live={live}
                  defaultOpen={filtered || i < OPEN_BY_DEFAULT}
                  onDecide={onDecide}
                />
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
