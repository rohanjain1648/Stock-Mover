import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";

export function PageLoading() {
  return (
    <div className="space-y-4" aria-busy="true" aria-label="Loading today's run">
      <Skeleton className="h-6 w-2/3 bg-secondary" />
      <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-5">
        {Array.from({ length: 5 }).map((_, i) => (
          <Skeleton key={i} className="h-20 bg-secondary" />
        ))}
      </div>
      <Skeleton className="h-40 bg-secondary" />
      <Skeleton className="h-40 bg-secondary" />
    </div>
  );
}

export function PageError({ onRetry }: { onRetry: () => void }) {
  return (
    <div className="rounded-xl border border-maroon/30 bg-card px-6 py-10 text-center">
      <h2 className="text-xl font-semibold">Could not load today's run</h2>
      <p className="mt-1 text-sm text-muted-foreground">Neither the live API nor the bundled snapshot answered.</p>
      <Button className="mt-4" onClick={onRetry}>
        Try again
      </Button>
    </div>
  );
}
