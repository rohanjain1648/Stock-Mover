# Demo video script (≤ 2:00)

Record with Loom or OBS at 1080p. Live app in one tab, GitHub Actions in a second, phone ready for the Fo call.
Speak over the screen; keep the mouse slow. Upload as **unlisted YouTube** or **Loom**; open the link in a private window before submitting.

| Time | Screen | Say |
|---|---|---|
| 0:00–0:12 | Today screen, top | "It's close of business on 31 October. Twenty Manyavar stores, one warehouse, and Diwali is eight days away. Stock Mover runs every morning and tells the merchandiser exactly what to move." |
| 0:12–0:30 | KPI strip → "0 rule breaks" badge | "Today: 278 moves in 25 cards, 2,014 units. Zero rule breaks — an independent validator replays every move before the list is published. 538 tiny moves wait for tomorrow so this takes ten minutes, not an hour." |
| 0:30–0:50 | Open the KNP-03 card, expand the first move | "First problem: KNP-03, a small Kanpur store, is at 208% of capacity — 300 sherwanis of one size landed there. 212 go back to the warehouse, the rest to stores that actually sell them. Every line says why, with the numbers." |
| 0:50–1:05 | KUR-04 card, then KUR-01 card | "A new launch selling 62 a day — and the Lucknow flagship holds none. Our bestseller KUR-01 is short for November, so every store gets a presentation minimum and the rest goes by need." |
| 1:05–1:20 | Findings tab → "Sold out — re-order, not slow" and "Not selling anywhere" | "Zero sales isn't always slow. Eight styles show no sales because they're sold out — we flag them for re-order. JKT-08 is in stock everywhere and genuinely isn't selling. We also catch bad data, like a store showing minus four in stock." |
| 1:20–1:35 | Approve all on a card → sign-off badge on a > ₹1 lakh move → Export CSV | "Approve a card in one click. Moves over one lakh are held for sign-off. Export the approved list for the warehouse." |
| 1:35–1:52 | Runs tab (07:00 runs + GitHub Actions run) → phone showing Fo call/text, or email digest | "And it runs on its own: 7 a.m. every day, plus a GitHub Action. The merchandiser gets the digest; each area manager gets at most five alerts a week — and Fo can call them." |
| 1:52–2:00 | Back to Today | "Velocity that knows a stock-out from a slow seller, festive-aware, rule-proof, explained. Stock Mover." |

Fallbacks: if the API is asleep, the app shows the snapshot banner — say "live data loads in the background". If Fo isn't signed in, show the email digest or `python scripts/dispatch_preview.py --run contracts/real_run.json` output instead.

## Two-line description (≤ 280 chars, for the form)
Stock Mover reads Manyavar's sales and stock every morning and finds stock in the wrong place. It produces a ranked list of warehouse sends, store-to-store moves and pull-backs, each explained in one line, checked against every rule, and ready to approve.
