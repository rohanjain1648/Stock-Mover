import { useState } from "react";
import { Check, ChevronDown, X } from "lucide-react";
import type { Group, Problem } from "@/types/run";
import { Button } from "@/components/ui/button";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { GroupRow } from "@/components/GroupRow";
import { Hint, LIVE_NEEDED } from "@/components/Hint";
import { inr, num, plural } from "@/lib/format";
import type { DecisionValue } from "@/lib/api";
import { cn } from "@/lib/utils";

export const KIND_LABEL: Record<string, string> = {
  CAPACITY: "Over capacity",
  OVERSTOCK: "Overstock",
  UNDERSTOCK: "Under-stocked",
  SCARCITY: "Short supply",
  NEW_LAUNCH: "New launch",
  MIN_DISPLAY: "Below minimum display",
  AGEING: "Ageing stock",
  SOLD_OUT_CONSOLIDATION: "Sold out at warehouse",
  OTHER: "Other",
};

const KIND_ACCENT: Record<string, string> = {
  CAPACITY: "border-l-maroon",
  OVERSTOCK: "border-l-maroon/70",
  UNDERSTOCK: "border-l-saffron",
  SCARCITY: "border-l-saffron",
  NEW_LAUNCH: "border-l-ok",
  AGEING: "border-l-ink/40",
  SOLD_OUT_CONSOLIDATION: "border-l-ok/70",
};

export function ProblemCard({
  problem,
  groups,
  live,
  defaultOpen,
  onDecide,
}: {
  problem: Problem;
  groups: Group[];
  live: boolean;
  defaultOpen: boolean;
  onDecide: (ids: string[], d: DecisionValue) => void;
}) {
  const [open, setOpen] = useState(defaultOpen);
  const units = groups.reduce((a, g) => a + (g.qty || 0), 0);
  const value = groups.reduce((a, g) => a + (g.mrp_value || 0), 0);
  const signoff = groups.filter((g) => g.needs_approval).length;
  const toApprove = groups.filter((g) => g.decision !== "approve").map((g) => g.group_id);
  const toReject = groups.filter((g) => g.decision !== "reject").map((g) => g.group_id);
  const decided = groups.filter((g) => g.decision).length;
  const hint = live ? null : LIVE_NEEDED;

  return (
    <section
      aria-labelledby={`p-${problem.problem_id}`}
      className={cn("overflow-hidden rounded-xl border border-l-4 bg-card shadow-sm", KIND_ACCENT[problem.kind] ?? "border-l-border")}
    >
      <Collapsible open={open} onOpenChange={setOpen}>
        <div className="flex flex-col gap-3 px-4 py-4 md:flex-row md:items-start md:justify-between">
          <div className="min-w-0 flex-1">
            <div className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
              {KIND_LABEL[problem.kind] ?? problem.kind}
            </div>
            <h2 id={`p-${problem.problem_id}`} className="mt-0.5 text-lg font-semibold leading-snug sm:text-xl">
              {problem.title}
            </h2>
            <p className="mt-1 text-sm text-muted-foreground">{problem.detail}</p>
            <p className="tnum mt-2 text-xs text-muted-foreground">
              <span className="font-medium text-foreground">{plural(groups.length, "move")}</span> · {num(units)} units · {inr(value)} at
              MRP{signoff > 0 && ` · ${signoff} need sign-off`}
              {decided > 0 && ` · ${decided} decided`}
            </p>
          </div>
          <div className="flex shrink-0 flex-wrap items-center gap-2">
            <Hint text={hint} disabled={!live}>
              <Button size="sm" disabled={!live || toApprove.length === 0} onClick={() => onDecide(toApprove, "approve")} className="bg-ok text-white hover:bg-ok/90">
                <Check className="mr-1 h-4 w-4" />
                Approve all {groups.length}
              </Button>
            </Hint>
            <Hint text={hint} disabled={!live}>
              <Button size="sm" variant="outline" disabled={!live || toReject.length === 0} onClick={() => onDecide(toReject, "reject")}>
                <X className="mr-1 h-4 w-4" />
                Reject all
              </Button>
            </Hint>
          </div>
        </div>
        <CollapsibleTrigger className="flex w-full items-center justify-center gap-1 border-t bg-secondary/40 px-4 py-1.5 text-xs font-medium text-muted-foreground hover:bg-secondary">
          <ChevronDown className={cn("h-3.5 w-3.5 transition-transform", open && "rotate-180")} />
          {open ? "Hide moves" : `Show ${plural(groups.length, "move")}`}
        </CollapsibleTrigger>
        <CollapsibleContent>
          <div className="border-t">
            {groups.map((g) => (
              <GroupRow key={g.group_id} g={g} live={live} onDecide={onDecide} />
            ))}
          </div>
        </CollapsibleContent>
      </Collapsible>
    </section>
  );
}
