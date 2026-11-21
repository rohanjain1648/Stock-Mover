import { AlertTriangle, Ban, Boxes, Sparkles, Warehouse } from "lucide-react";
import type { Flag } from "@/types/run";
import { RunHeader } from "@/components/RunHeader";
import { PageError, PageLoading } from "@/components/PageState";
import { useRun } from "@/lib/useRun";
import { num } from "@/lib/format";

const SECTIONS: { kind: string; title: string; blurb: string; icon: typeof AlertTriangle; tone: string }[] = [
  { kind: "DATA_QUALITY", title: "Data to fix", blurb: "Records that do not add up. The engine works around them; a stock count fixes them.", icon: AlertTriangle, tone: "text-maroon bg-maroon/10" },
  { kind: "REORDER", title: "Sold out — re-order, not slow", blurb: "Zero sales here because there was nothing to sell. These need buying, not marking down.", icon: Boxes, tone: "text-saffron bg-saffron/10" },
  { kind: "DEAD_STOCK", title: "Not selling anywhere", blurb: "On shelves across the chain and still not moving. Consolidate or mark down; do not re-order.", icon: Ban, tone: "text-ink bg-ink/10" },
  { kind: "NEW_STORE", title: "New store", blurb: "Too little history for its own rate; it borrows the rate of similar stores.", icon: Sparkles, tone: "text-ok bg-ok/10" },
  { kind: "CAPACITY", title: "Over capacity", blurb: "Stores holding more than they can display. Nothing more is sent until the excess moves out.", icon: Warehouse, tone: "text-maroon bg-maroon/10" },
];

function FlagItem({ f }: { f: Flag }) {
  const where = [f.location_id, f.sku_id ?? f.style_id].filter(Boolean).join(" · ");
  return (
    <li className="flex flex-col gap-1 border-t px-4 py-3 first:border-t-0 sm:flex-row sm:gap-4">
      {where && <span className="shrink-0 font-mono text-xs font-medium text-muted-foreground sm:w-40">{where}</span>}
      <span className="text-sm leading-snug">{f.message}</span>
    </li>
  );
}

export default function Findings() {
  const q = useRun();
  const run = q.data?.run;
  if (q.isLoading) return <PageLoading />;
  if (!run) return <PageError onRetry={() => q.refetch()} />;

  const flags = run.flags ?? [];
  const known = new Set(SECTIONS.map((s) => s.kind));
  const other = flags.filter((f) => !known.has(f.kind));
  const sections = [...SECTIONS, ...(other.length ? [{ kind: "__OTHER", title: "Other findings", blurb: "", icon: AlertTriangle, tone: "text-ink bg-ink/10" }] : [])];

  return (
    <div className="space-y-6">
      <RunHeader showExport={false} />
      <div>
        <h1 className="text-2xl font-semibold sm:text-3xl">Findings</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          What the run noticed that is not a move: {num(flags.length)} findings. A product with zero sales is not always a slow product.
        </p>
      </div>
      {flags.length === 0 && <p className="rounded-xl border border-dashed bg-card px-6 py-10 text-center text-sm">No findings in this run.</p>}
      {sections.map(({ kind, title, blurb, icon: Icon, tone }) => {
        const items = kind === "__OTHER" ? other : flags.filter((f) => f.kind === kind);
        if (items.length === 0) return null;
        return (
          <section key={kind} aria-labelledby={`f-${kind}`} className="overflow-hidden rounded-xl border bg-card shadow-sm">
            <div className="flex items-start gap-3 px-4 py-3.5">
              <span className={`grid h-9 w-9 shrink-0 place-items-center rounded-lg ${tone}`}>
                <Icon className="h-5 w-5" aria-hidden />
              </span>
              <div className="min-w-0">
                <div className="flex items-baseline gap-2">
                  <h2 id={`f-${kind}`} className="text-lg font-semibold">
                    {title}
                  </h2>
                  <span className="tnum text-sm text-muted-foreground">{num(items.length)}</span>
                </div>
                {blurb && <p className="text-sm text-muted-foreground">{blurb}</p>}
              </div>
            </div>
            <ul className="border-t">
              {items.map((f) => (
                <FlagItem key={f.flag_id} f={f} />
              ))}
            </ul>
          </section>
        );
      })}
    </div>
  );
}
