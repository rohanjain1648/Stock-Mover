# S5 · Update from S0 (13:25) — trimmed scope, real data

It is 13:25 and nothing from the frontend is on `main` yet. The live link is the demo. **Ship order (stop after any step if time runs out — each step is shippable):**

1. **Task 1** (scaffold, types, api with snapshot fallback, format) — but copy **`contracts/real_run.json`** (a real validated run: 278 groups, 28 problem cards, 38 flags) to `frontend/public/sample_run.json`, not the old hand-made sample. Push.
2. **Task 2** (Today screen) — the core. Problem cards in the order the run gives them; cards with > 8 groups show the first 8 + "Show all N". Card header has **Approve all**. Show `summary.deferred` as a muted line under the KPI strip: "538 small moves (₹15.3 L) deferred to tomorrow's run". Push.
3. **Task 4** (Vercel deploy) — do this **right after Task 2**, before Task 3. Live link first.
4. **Task 3, trimmed:** a single **Findings** tab (flags grouped by kind — the REORDER group "Sold out — re-order, not slow" must be visible: judges check that zero sales ≠ slow) and a small **Runs** tab ("Runs on its own: 07:00 IST daily + GitHub Actions", run history, notification log). Skip the Stores page unless time remains (a compact store table is enough).

Deadlines: step 2 pushed by **14:30**, live on Vercel by **14:50**, freeze **15:30**.
Test in `Today.test.tsx` against the real run: `findByText(/KNP-03 is at 208% of capacity/)` and `getByText(/0 rule breaks/)` both hold for `real_run.json`.
