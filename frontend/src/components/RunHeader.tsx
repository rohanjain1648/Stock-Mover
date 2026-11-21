import { CloudOff, Download, Loader2, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Hint } from "@/components/Hint";
import { exportUrl } from "@/lib/api";
import { istDateTime, longDate, triggerLabel } from "@/lib/format";
import { useRun } from "@/lib/useRun";
import { cn } from "@/lib/utils";

/** As-of date, last run + trigger, rule badge and export. Shown at the top of every page. */
export function RunHeader({ showExport = true }: { showExport?: boolean }) {
  const { data, isFetching, refetch } = useRun();
  if (!data) return null;
  const { run, source } = data;
  const live = source === "live";
  const breaks = run.validation?.violations?.length ?? 0;
  const passed = (run.validation?.passed ?? breaks === 0) && breaks === 0;
  const approved = (run.groups ?? []).filter((g) => g.decision === "approve").length;

  return (
    <div className="space-y-3">
      {!live && (
        <div
          role="status"
          className="flex flex-col gap-3 rounded-lg border border-saffron/40 bg-saffron/10 px-4 py-3 text-sm sm:flex-row sm:items-center sm:justify-between"
        >
          <div className="flex items-start gap-2.5">
            <CloudOff className="mt-0.5 h-4 w-4 shrink-0 text-saffron" aria-hidden />
            <p>
              <strong className="font-semibold">Snapshot</strong> of the {longDate(run.as_of)} run. The live API is waking up
              (this can take up to a minute); approving and export switch on as soon as it answers.
            </p>
          </div>
          <Button size="sm" variant="outline" className="shrink-0 bg-card" onClick={() => refetch()} disabled={isFetching}>
            {isFetching ? <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="mr-1.5 h-3.5 w-3.5" />}
            Retry live
          </Button>
        </div>
      )}

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <dl className="flex flex-wrap items-center gap-x-3 gap-y-1.5 text-sm text-muted-foreground">
          <div className="flex gap-1">
            <dt>As of</dt>
            <dd className="font-medium text-foreground">{longDate(run.as_of)}</dd>
          </div>
          <span aria-hidden>·</span>
          <div className="flex gap-1">
            <dt>Ran</dt>
            <dd className="font-medium text-foreground">
              {istDateTime(run.generated_at)} IST · {triggerLabel(run.trigger)}
            </dd>
          </div>
          <span aria-hidden>·</span>
          <dd>
            <Hint text={`The independent rule checker re-checked all ${run.validation?.checked_moves ?? 0} SKU moves against every business rule.`}>
              <span
                className={cn(
                  "inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-semibold",
                  passed ? "bg-ok/10 text-ok" : "bg-maroon/10 text-maroon",
                )}
              >
                <span className={cn("h-1.5 w-1.5 rounded-full", passed ? "bg-ok" : "bg-maroon")} aria-hidden />
                {breaks} rule {breaks === 1 ? "break" : "breaks"}
              </span>
            </Hint>
          </dd>
        </dl>

        {showExport &&
          (live ? (
            <Button asChild size="sm" className="self-start sm:self-auto">
              <a href={exportUrl("approved")} download>
                <Download className="mr-1.5 h-3.5 w-3.5" />
                Export approved CSV{approved ? ` (${approved})` : ""}
              </a>
            </Button>
          ) : (
            <Hint text="Live API needed to export decisions" disabled>
              <Button size="sm" disabled className="self-start sm:self-auto">
                <Download className="mr-1.5 h-3.5 w-3.5" />
                Export approved CSV
              </Button>
            </Hint>
          ))}
      </div>
    </div>
  );
}
