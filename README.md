# Stock Mover

**Right stock. Right store. Right size.** · Manyavar (Vedant Fashions) × Calcutta AI Club hackathon, Problem B.

Every morning Stock Mover reads Manyavar's sales and stock, finds stock in the wrong place, and hands the
merchandiser a ranked, ready-to-approve list of **warehouse sends, store-to-store moves and pull-backs** —
each explained in one line, checked against every rule, and delivered to the people who act on it.

- **Live app:** _VERCEL_URL_ · **API:** _RENDER_URL_/api/health
- Design: [docs/superpowers/specs/2026-11-21-stock-mover-design.md](docs/superpowers/specs/2026-11-21-stock-mover-design.md) · Contracts: [contracts/CONTRACTS.md](contracts/CONTRACTS.md)

## What today's run finds (data as of close 31 Oct 2026)

| | |
|---|---|
| Moves to approve | **278** groups (583 SKU lines, 2,014 units, ₹1.78 Cr at MRP) in **25 problem cards** |
| Rule breaks | **0** — an independent validator replays every move; the run refuses to publish otherwise |
| Revenue protected | ₹89 L of festive-season sales at risk covered; 21 moves > ₹1 lakh flagged for sign-off |
| Kept short | 538 small moves (< ₹10,000 at risk, ₹15.3 L total) deferred to tomorrow's run — the list keeps 88% of the value |

**The stock problems it surfaces**
- **KNP-03 at 208% of capacity** — 300 × SHW-02-L landed in a B store that sold 1 in a year → 212 back to the warehouse, the rest to stores that sell it.
- **New launch KUR-04 missing at the flagship** — selling 62/day chain-wide, LKO-01 (S++) and MZF-01 hold none → 128 and 26 units.
- **KUR-01 bestseller short for November** — 648 units for 1,097 units of need → presentation minimum everywhere, rest by need × velocity.
- **MZF-01 starved** — 37% of capacity, 29 days of cover, Mojari below minimum display.
- **Zero sales ≠ slow** — KUR-12/15/18/24, MOJ-03/06, JKT-06, STL-03 sold out chain-wide: flagged for re-order, never pulled back; JKT-08 and four others are genuinely dead (in stock everywhere, not selling).
- **Ageing stock** older than 180 days (90 for fashion) moved to stores that sell it before the wedding season ends (12 Dec).
- **Data that can't be trusted** — MYS-02 KUR-02-M at −4 on hand; 191 units sold in weeks recorded as out of stock.

## How it works

1. **Velocity, de-censored** — sales ÷ days the SKU was actually on the shelf (from `stock_weekly`), not calendar days; sparse SKUs shrink toward peer stores; never-stocked stores borrow from peers only if they range the style; the brand-new BLR-05 uses peer B stores.
2. **Season-aware** — a festive lift per state from last year's Diwali-to-weddings season (Bihar 2.48×, UP 2.34×, Karnataka 1.95×): Diwali 8 Nov and 11 wedding days fall in the next 30 days. A plain 90-day average would under-send ~2.7×.
3. **Positions** — cover = (on hand + in transit) ÷ velocity; need = lead time + 7 review + 7 safety days, raised to minimum display.
4. **Moves** — one ledger, five passes: capacity/overstock → store-to-store → warehouse allocation under scarcity (by date, inbound-aware) → minimum display → ageing.
5. **Rules enforced** — minimum display, S++ top-20 protection, capacity, in-transit, 30-day donor cover (style level), lead times; > ₹1 lakh needs sign-off.
6. **Explained** — every line is built from the numbers, e.g. *"WH → LKO-01 · 128 × KUR-04 (M27 L50 XL34 XXL17): new launch (20 Sep) selling 62.2/day chain-wide; LKO-01 holds 0; similar stores sell 7.0/day."*
7. **Runs on its own** — 07:00 IST scheduler in the API + a daily GitHub Action; email digest to the merchandiser, ≤ 5 alerts per area manager per week (their `max_alerts_per_week`), and a Claude Code skill that hands the day's alerts to **Fo (Wajo)** to email, text or call.

## Run it
```bash
pip install -r requirements.txt
python -m engine.run              # strict: refuses to publish if any rule is broken
pytest -q && pytest -q backend/tests
uvicorn backend.app.main:app --port 8000
cd frontend && npm install && npm run dev
```

## Layout
```
engine/      data · velocity · position · moves · explain · rules (validator) · quality (flags) · run
backend/     FastAPI: runs, decisions, CSV export, notifications, 07:00 scheduler
frontend/    React approval console
contracts/   frozen interfaces, sample + real run
data/csv/    the 17 Manyavar tables (synthetic, as supplied)
```
Built in one day by five parallel Claude Code sessions working from contract-first plans ([docs/plans/](docs/plans/)).
