import { NavLink, Outlet } from "react-router-dom";
import { ArrowLeftRight, ClipboardList, History, SearchCheck, Store } from "lucide-react";
import { Toaster } from "@/components/ui/sonner";
import { cn } from "@/lib/utils";

const NAV = [
  { to: "/", label: "Today", icon: ClipboardList, end: true },
  { to: "/stores", label: "Stores", icon: Store, end: false },
  { to: "/findings", label: "Findings", icon: SearchCheck, end: false },
  { to: "/runs", label: "Runs", icon: History, end: false },
];

export function AppShell() {
  return (
    <div className="min-h-screen bg-background">
      <header className="sticky top-0 z-30 border-b bg-background/90 backdrop-blur supports-[backdrop-filter]:bg-background/75">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-x-4 gap-y-1 px-4 py-2.5">
          <NavLink to="/" className="flex items-center gap-2">
            <span className="grid h-8 w-8 place-items-center rounded-lg bg-saffron text-cream">
              <ArrowLeftRight className="h-4 w-4" aria-hidden />
            </span>
            <span className="leading-tight">
              <span className="block font-display text-lg font-semibold">Stock Mover</span>
              <span className="hidden text-[11px] text-muted-foreground sm:block">Manyavar · daily stock moves</span>
            </span>
          </NavLink>
          <nav aria-label="Main" className="-mx-1 flex w-full items-center gap-0.5 sm:mx-0 sm:w-auto">
            {NAV.map(({ to, label, icon: Icon, end }) => (
              <NavLink
                key={to}
                to={to}
                end={end}
                className={({ isActive }) =>
                  cn(
                    "inline-flex flex-1 items-center justify-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground sm:flex-none",
                    isActive && "bg-secondary text-foreground",
                  )
                }
              >
                <Icon className="h-4 w-4" aria-hidden />
                {label}
              </NavLink>
            ))}
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-4 py-5 sm:py-6">
        <Outlet />
      </main>
      <footer className="mx-auto max-w-6xl px-4 pb-8 text-xs text-muted-foreground">
        Runs on its own every day at 07:00 IST. Every move is re-checked by an independent rule checker before it is shown.
      </footer>
      <Toaster position="bottom-center" richColors />
    </div>
  );
}
