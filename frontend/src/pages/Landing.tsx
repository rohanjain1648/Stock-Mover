import { lazy, Suspense } from "react";
import { Link } from "react-router-dom";
import {
  ArrowRight, Brain, CalendarHeart, CheckCircle2, PhoneCall, PlayCircle, ShieldCheck, Sparkles, Truck,
} from "lucide-react";

const Warehouse3D = lazy(() => import("@/components/landing/Warehouse3D"));

const STATS = [
  { v: "278", l: "moves to approve today" },
  { v: "0", l: "rule breaks, independently verified" },
  { v: "₹89 L", l: "festive sales protected" },
  { v: "10 min", l: "to approve the whole list" },
];

const PROBLEMS = [
  { t: "KNP-03 is at 208% of capacity", d: "300 sherwanis of one size landed in a small Kanpur store that sold one all year. 212 go back, the rest go where they sell." },
  { t: "A new launch missing at the flagship", d: "KUR-04 sells 62 a day chain-wide — Lucknow's S++ store held none. 128 units are on their way." },
  { t: "Sold out is not slow", d: "Eight bestsellers show zero sales only because they ran out. Flagged for re-order, never pulled back." },
  { t: "A bestseller short before Diwali", d: "648 units for 1,097 units of need: every store gets a minimum, the rest goes by need × velocity." },
];

const STEPS = [
  { i: Brain, t: "Velocity that knows a stock-out", d: "Sales ÷ days actually on the shelf, borrowed from peer stores when data is thin." },
  { i: CalendarHeart, t: "Festive-aware", d: "Per-state lift from Diwali and wedding dates: Bihar 2.48×, UP 2.34×, Karnataka 1.95×." },
  { i: Truck, t: "Five passes, one ledger", d: "Capacity → store-to-store → warehouse under scarcity → minimum display → ageing." },
  { i: ShieldCheck, t: "Rule-proof", d: "An independent validator replays every move against all 10 rules before anything is published." },
  { i: CheckCircle2, t: "Explained in one line", d: "Every move quotes its numbers — built from data, never invented." },
  { i: PhoneCall, t: "Runs on its own", d: "7 a.m. daily, email digest, ≤ 5 alerts per manager a week — and Fo calls for sign-off." },
];

export default function Landing() {
  return (
    <div className="space-y-20 pb-20">
      {/* hero */}
      <section className="grid items-center gap-8 pt-8 lg:grid-cols-[1fr_1.15fr]">
        <div className="space-y-6">
          <span className="inline-flex items-center gap-1.5 rounded-full bg-secondary px-3 py-1 text-xs font-medium">
            <Sparkles className="h-3.5 w-3.5 text-saffron" aria-hidden /> Manyavar × Calcutta AI Club · Problem B
          </span>
          <h1 className="font-display text-4xl font-semibold leading-tight sm:text-5xl">
            Right stock. Right store. <span className="text-saffron">Right size.</span>
          </h1>
          <p className="max-w-xl text-lg text-muted-foreground">
            Every morning Stock Mover reads Manyavar's sales and stock, finds what's in the wrong place, and hands the
            merchandiser a ranked, rule-checked list of warehouse sends, store moves and pull-backs — each explained in
            one line, ready to approve.
          </p>
          <div className="flex flex-wrap gap-3">
            <Link to="/" className="inline-flex items-center gap-2 rounded-md bg-saffron px-5 py-2.5 font-medium text-cream hover:opacity-90">
              Open today's moves <ArrowRight className="h-4 w-4" aria-hidden />
            </Link>
            <a href="https://youtu.be/47XpvHJ0fFg" target="_blank" rel="noreferrer"
               className="inline-flex items-center gap-2 rounded-md border px-5 py-2.5 font-medium hover:bg-secondary">
              <PlayCircle className="h-4 w-4" aria-hidden /> Watch the 2-min demo
            </a>
          </div>
        </div>
        <div className="relative h-[380px] overflow-hidden rounded-2xl border bg-card shadow-sm sm:h-[460px]">
          <Suspense fallback={<div className="grid h-full place-items-center text-sm text-muted-foreground">Loading the digital twin…</div>}>
            <Warehouse3D />
          </Suspense>
          <div className="pointer-events-none absolute bottom-3 left-3 flex flex-wrap gap-2 text-[11px]">
            <Legend c="#2f6f6a" l="healthy" /><Legend c="#f59e0b" l="starved" /><Legend c="#dc2626" l="over capacity" />
            <Legend c="#f4c542" l="forklift on a move" />
          </div>
          <span className="pointer-events-none absolute right-3 top-3 rounded bg-background/80 px-2 py-0.5 text-[11px] text-muted-foreground">
            Digital twin · drag to rotate
          </span>
        </div>
      </section>

      {/* stats */}
      <section className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {STATS.map((s) => (
          <div key={s.l} className="rounded-xl border bg-card p-5">
            <div className="font-display text-3xl font-semibold">{s.v}</div>
            <div className="mt-1 text-sm text-muted-foreground">{s.l}</div>
          </div>
        ))}
      </section>

      {/* problem */}
      <section className="space-y-6">
        <Heading k="The problem" t="Stock in the wrong place, right before Diwali" />
        <p className="max-w-3xl text-muted-foreground">
          20 stores, one warehouse, two years of bills — and 11 wedding days in the next month. Stock-outs hide demand,
          weekly top-ups miss the peak, and a plain 90-day average would under-send by 2.7×. Here's what the data was hiding:
        </p>
        <div className="grid gap-4 md:grid-cols-2">
          {PROBLEMS.map((p) => (
            <div key={p.t} className="rounded-xl border bg-card p-5 shadow-sm">
              <h3 className="font-display text-lg font-semibold">{p.t}</h3>
              <p className="mt-1.5 text-sm text-muted-foreground">{p.d}</p>
            </div>
          ))}
        </div>
      </section>

      {/* how */}
      <section className="space-y-6">
        <Heading k="How it works" t="From two years of bills to a ten-minute decision" />
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {STEPS.map(({ i: Icon, t, d }, n) => (
            <div key={t} className="rounded-xl border bg-card p-5">
              <div className="flex items-center gap-2">
                <span className="grid h-8 w-8 place-items-center rounded-lg bg-secondary text-saffron"><Icon className="h-4 w-4" aria-hidden /></span>
                <span className="text-xs font-medium text-muted-foreground">0{n + 1}</span>
              </div>
              <h3 className="mt-3 font-semibold">{t}</h3>
              <p className="mt-1 text-sm text-muted-foreground">{d}</p>
            </div>
          ))}
        </div>
      </section>

      {/* sample line */}
      <section className="rounded-2xl bg-ink p-6 text-cream sm:p-8" style={{ backgroundColor: "#2b2622" }}>
        <p className="text-xs uppercase tracking-wider opacity-70">Every move, one line</p>
        <p className="mt-3 font-mono text-sm leading-relaxed sm:text-base">
          WH → LKO-01 · 128 × KUR-04 (M27 L50 XL34 XXL17): new launch (20 Sep) selling 62.2/day chain-wide;
          LKO-01 holds 0; similar stores sell 7.0/day.
        </p>
      </section>

      {/* cta */}
      <section className="flex flex-col items-center gap-4 text-center">
        <h2 className="font-display text-3xl font-semibold">You know where demand comes from.</h2>
        <p className="max-w-xl text-muted-foreground">Weddings and festivals. Stock Mover makes sure the stock is waiting when it does.</p>
        <div className="flex flex-wrap justify-center gap-3">
          <Link to="/" className="inline-flex items-center gap-2 rounded-md bg-saffron px-5 py-2.5 font-medium text-cream">
            Approve today's list <ArrowRight className="h-4 w-4" aria-hidden />
          </Link>
          <a href="https://github.com/rohanjain1648/Stock-Mover" target="_blank" rel="noreferrer"
             className="rounded-md border px-5 py-2.5 font-medium hover:bg-secondary">View the code</a>
        </div>
      </section>
    </div>
  );
}

function Heading({ k, t }: { k: string; t: string }) {
  return (
    <div>
      <p className="text-xs font-medium uppercase tracking-wider text-saffron">{k}</p>
      <h2 className="mt-1 font-display text-3xl font-semibold">{t}</h2>
    </div>
  );
}

function Legend({ c, l }: { c: string; l: string }) {
  return (
    <span className="inline-flex items-center gap-1 rounded bg-background/85 px-1.5 py-0.5">
      <span className="h-2 w-2 rounded-sm" style={{ backgroundColor: c }} /> {l}
    </span>
  );
}
