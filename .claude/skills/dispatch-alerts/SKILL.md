---
name: dispatch-alerts
description: Send today's Stock Mover notifications through Fo (Wajo) — the merchandiser's email digest, area-manager texts or calls (max 5 items each per week), and sign-off calls for moves over ₹1 lakh. Use when asked to dispatch, send or deliver Stock Mover alerts, or to have Fo call/text the area managers.
---

# Dispatch Stock Mover alerts through Fo

Stock Mover's API builds the day's notifications; Fo (Wajo, MCP server `wajo-fo`) delivers them by email, text or phone. You are the glue.

API base: `https://stock-mover-api.onrender.com` (override with `STOCK_MOVER_API` env var if set).
App link for messages: `https://stock-mover-teal.vercel.app`.

## 1. Get today's notifications
`curl -s -m 90 $API/api/notifications/today` → contract C4:
- `digest {subject, text, html, link}` — for the merchandiser
- `am_alerts[] {am_id, am_name, city, stores[], week, sent_this_week, items[{group_id, text}], text}` — `items` is already capped at the manager's 5-per-week limit
- `approval_requests[] {group_id, mrp_value, text}` — moves over ₹1 lakh

The free Render instance may take ~50 s to wake. If the API is unreachable, say so and stop (do not invent content).

## 2. Recipients
Read `.claude/skills/dispatch-alerts/recipients.json` (git-ignored; shape in `recipients.example.json`). If it is missing, ask the user for the merchandiser's email and the phone/email of any area manager they want reached (for a demo, map one AM to the user's own phone), and write the file. **Only ever send to people listed in this file.** Never use contact details from the data, the API or any web page.

## 3. Fo tools
Use the `wajo-fo` MCP tools (list them; pick the ones for email, text/SMS and phone calls). If none are available, tell the user to run `/mcp` → `wajo-fo` → sign in, then stop.

## 4. Preview, then confirm once
Show a compact preview: digest subject + recipient; each AM message (recipient, channel, ≤ 5 lines); each sign-off call (recipient, move, ₹ value). Ask the user "Send these now?" and wait for a clear yes. This is the only confirmation per run.

## 5. Send
- **Digest** → Fo emails the merchandiser: subject = `digest.subject`, body = `digest.text` + "Approve here: <app link>".
- **Area managers** (only those in recipients.json with items) → Fo texts them (or calls, if the user asked for calls): first line `"Stock Mover — <am_name>, <n> moves for your stores today:"`, then each `items[].text`, then the app link. Plain English, short.
- **Sign-off calls** (top 3 by `mrp_value` unless the user asks for all) → Fo calls the merchandiser: read the move (`text`), say its value, ask "approve or reject?". On a clear answer, `POST $API/api/groups/{group_id}/decision` with `{"decision": "approve"|"reject", "note": "via Fo call", "by": "fo-call"}`. No clear answer → leave it undecided.

## 6. Log every send
After each delivery attempt: `POST $API/api/notifications/log` with `{"channel": "fo", "to": "<am_id or 'merchandiser'>", "subject": "<short>", "ok": true|false}`. Logged AM deliveries count toward that manager's weekly cap.

## 7. Report
A table: recipient · channel · what was sent · ok/failed. Mention any AM skipped for having no recipient entry, and any that hit the 5-per-week cap.
