import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { decide, decideMany, fetchLatest, type DecisionValue, type Source } from "./api";
import type { Run } from "@/types/run";

export const RUN_KEY = ["run", "latest"] as const;
type RunData = { run: Run; source: Source };

/** The latest run. While on the snapshot, keep knocking on the live API every 20 s. */
export function useRun() {
  return useQuery({
    queryKey: RUN_KEY,
    queryFn: fetchLatest,
    staleTime: 60_000,
    refetchOnWindowFocus: false,
    refetchInterval: (q) => (q.state.data?.source === "snapshot" ? 20_000 : false),
  });
}

function patchDecisions(data: RunData | undefined, ids: Set<string>, decision: DecisionValue | null): RunData | undefined {
  if (!data) return data;
  return {
    ...data,
    run: { ...data.run, groups: data.run.groups.map((g) => (ids.has(g.group_id) ? { ...g, decision } : g)) },
  };
}

/** Approve/reject one or many moves: optimistic, rolled back with a toast if the API refuses. */
export function useDecide() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ ids, decision }: { ids: string[]; decision: DecisionValue }) => {
      if (ids.length === 1) {
        await decide(ids[0], decision);
        return 1;
      }
      return decideMany(ids, decision);
    },
    onMutate: async ({ ids, decision }) => {
      await qc.cancelQueries({ queryKey: RUN_KEY });
      const prev = qc.getQueryData<RunData>(RUN_KEY);
      qc.setQueryData<RunData>(RUN_KEY, (d) => patchDecisions(d, new Set(ids), decision));
      return { prev };
    },
    onError: (err, { ids }, ctx) => {
      if (ctx?.prev) qc.setQueryData(RUN_KEY, ctx.prev);
      toast.error(`Could not record ${ids.length === 1 ? "the decision" : `${ids.length} decisions`}`, {
        description: err instanceof Error ? err.message : "The live API did not answer.",
      });
    },
    onSuccess: (_n, { ids, decision }) => {
      const verb = decision === "approve" ? "Approved" : "Rejected";
      toast.success(ids.length === 1 ? `${verb} ${ids[0]}` : `${verb} ${ids.length} moves`);
    },
  });
}
