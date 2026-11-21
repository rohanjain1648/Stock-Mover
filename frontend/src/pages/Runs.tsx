import { useQuery } from "@tanstack/react-query";
import { CalendarClock, CheckCircle2, GitBranch, Mail, MessageCircle, ShieldCheck, XCircle } from "lucide-react";
import type { NotificationLogItem, RunListItem } from "@/types/run";
import { RunHeader } from "@/components/RunHeader";
import { PageError, PageLoading } from "@/components/PageState";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { fetchNotificationLog, fetchRuns } from "@/lib/api";
import { useRun } from "@/lib/useRun";
import { istDateTime, num, triggerLabel } from "@/lib/format";

function Passed({ ok }: { ok: boolean }) {
  return ok ? (
    <span className="inline-flex items-center gap-1 text-ok">
      <CheckCircle2 className="h-4 w-4" aria-hidden /> 0 rule breaks
    </span>
  ) : (
    <span className="inline-flex items-center gap-1 text-maroon">
      <XCircle className="h-4 w-4" aria-hidden /> Refused
    </span>
  );
}

export default function Runs() {
  const q = useRun();
  const live = q.data?.source === "live";
  const runs = useQuery({ queryKey: ["runs", live], queryFn: fetchRuns, enabled: q.isSuccess, retry: false });
  const log = useQuery({ queryKey: ["notifications-log", live], queryFn: fetchNotificationLog, enabled: q.isSuccess, retry: false });

  if (q.isLoading) return <PageLoading />;
  const run = q.data?.run;
  if (!run) return <PageError onRetry={() => q.refetch()} />;

  const history: RunListItem[] = runs.data?.length
    ? runs.data
    : [{ run_id: run.run_id, generated_at: run.generated_at, trigger: run.trigger, n_groups: run.summary?.n_groups ?? run.groups?.length ?? 0, passed: run.validation?.passed ?? true }];
  const notes: NotificationLogItem[] = log.data ?? [];

  return (
    <div className="space-y-6">
      <RunHeader showExport={false} />
      <div>
        <h1 className="text-2xl font-semibold sm:text-3xl">Runs</h1>
      </div>

      <section className="rounded-xl border bg-card p-4 shadow-sm sm:p-5">
        <h2 className="text-lg font-semibold">Runs on its own</h2>
        <ul className="mt-3 grid gap-3 text-sm sm:grid-cols-3">
          <li className="flex gap-2.5">
            <CalendarClock className="mt-0.5 h-4 w-4 shrink-0 text-saffron" aria-hidden />
            <span>Every day at 07:00 IST, by the scheduler on the API server.</span>
          </li>
          <li className="flex gap-2.5">
            <GitBranch className="mt-0.5 h-4 w-4 shrink-0 text-saffron" aria-hidden />
            <span>And via GitHub Actions, as a second trigger that also keeps the server awake.</span>
          </li>
          <li className="flex gap-2.5">
            <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-ok" aria-hidden />
            <span>Each run goes live only if the rule checker finds 0 breaks; otherwise the previous list stays.</span>
          </li>
        </ul>
      </section>

      <section className="space-y-2">
        <h2 className="text-lg font-semibold">History</h2>
        {!runs.data?.length && (
          <p className="text-xs text-muted-foreground">{live ? "Only the current run so far." : "Showing the current run; full history needs the live API."}</p>
        )}
        <div className="overflow-x-auto rounded-xl border bg-card shadow-sm">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Ran (IST)</TableHead>
                <TableHead>Trigger</TableHead>
                <TableHead className="text-right">Moves</TableHead>
                <TableHead>Rule check</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {history.map((r) => (
                <TableRow key={r.run_id}>
                  <TableCell className="tnum whitespace-nowrap">{istDateTime(r.generated_at)}</TableCell>
                  <TableCell>{triggerLabel(r.trigger)}</TableCell>
                  <TableCell className="tnum text-right">{num(r.n_groups)}</TableCell>
                  <TableCell className="whitespace-nowrap">
                    <Passed ok={r.passed} />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      </section>

      <section className="space-y-2">
        <h2 className="text-lg font-semibold">Notifications sent</h2>
        <p className="text-xs text-muted-foreground">Morning digest by email to the merchandiser; area-manager alerts through Fo.</p>
        {log.isError || (!live && !log.data) ? (
          <p className="rounded-xl border border-dashed bg-card px-4 py-6 text-center text-sm text-muted-foreground">
            The notification log needs the live API.
          </p>
        ) : notes.length === 0 ? (
          <p className="rounded-xl border border-dashed bg-card px-4 py-6 text-center text-sm text-muted-foreground">Nothing sent yet today.</p>
        ) : (
          <div className="overflow-x-auto rounded-xl border bg-card shadow-sm">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Sent (IST)</TableHead>
                  <TableHead>Channel</TableHead>
                  <TableHead>To</TableHead>
                  <TableHead>Subject</TableHead>
                  <TableHead>Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {notes.map((n, i) => (
                  <TableRow key={`${n.sent_at}-${i}`}>
                    <TableCell className="tnum whitespace-nowrap">{istDateTime(n.sent_at)}</TableCell>
                    <TableCell className="whitespace-nowrap">
                      <span className="inline-flex items-center gap-1.5">
                        {n.channel === "fo" ? <MessageCircle className="h-4 w-4" aria-hidden /> : <Mail className="h-4 w-4" aria-hidden />}
                        {n.channel === "fo" ? "Fo" : n.channel === "email" ? "Email" : n.channel}
                      </span>
                    </TableCell>
                    <TableCell className="max-w-[12rem] truncate">{n.to}</TableCell>
                    <TableCell className="min-w-[12rem]">{n.subject}</TableCell>
                    <TableCell className="whitespace-nowrap">{n.ok ? <span className="text-ok">Sent</span> : <span className="text-maroon">Failed</span>}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </section>
    </div>
  );
}
