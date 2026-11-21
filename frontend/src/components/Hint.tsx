import type { ReactNode } from "react";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";

/**
 * Tooltip that also works on disabled buttons (they swallow pointer events,
 * so the trigger is a focusable wrapper). Carries its own provider so pages
 * render standalone in tests.
 */
export function Hint({ text, children, disabled = false }: { text?: string | null; children: ReactNode; disabled?: boolean }) {
  if (!text) return <>{children}</>;
  return (
    <TooltipProvider delayDuration={150}>
      <Tooltip>
        <TooltipTrigger asChild>
          {disabled ? (
            <span tabIndex={0} className="inline-flex cursor-not-allowed rounded-md focus:outline-none focus-visible:ring-2 focus-visible:ring-ring">
              {children}
            </span>
          ) : (
            children
          )}
        </TooltipTrigger>
        <TooltipContent className="max-w-xs text-xs">{text}</TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}

export const LIVE_NEEDED = "Live API needed to record decisions";
