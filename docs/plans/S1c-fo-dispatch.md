# S1c · Fo (Wajo) dispatch skill — notifications that act on their own

> You are **S1** again (same shared-folder git rules). REQUIRED SUB-SKILL: superpowers:executing-plans. Push by **14:45 IST**.

**Why:** "Runs on its own" is judged. The backend already builds the day's notifications (`GET /api/notifications/today`, contract C4: digest, ≤5 alerts per area manager per week, approval requests for moves > ₹1 lakh) and emails them via Gmail when configured. Fo by Wajo (MCP server `wajo-fo`, `https://mcp.api.wajo.ai/fo`, already added to Claude Code config by the user) can **email, text and phone** people. This task makes a Claude Code skill that hands the day's notifications to Fo, and records what was sent.

**You own (new):** `.claude/skills/dispatch-alerts/SKILL.md`, `scripts/dispatch_preview.py`, `tests/test_dispatch_preview.py`.

## Tasks
- [ ] **Preview script (works without Fo — the fallback for the demo).** `scripts/dispatch_preview.py [--api URL | --run contracts/real_run.json]`: if `--api`, GET `/api/notifications/today`; else build C4 locally by importing `backend.app.notify.build_notifications(run, ams, sent_counts={})` with `ams` from `engine.data.load_data().area_managers` (adapt to the function's real signature in `backend/app/notify.py`). Print three sections — EMAIL (subject + first 10 lines), AREA MANAGER MESSAGES (one block per AM, ≤5 items each), SIGN-OFF CALLS (one line per > ₹1 lakh group). Test: running on `contracts/real_run.json` prints each section and every AM block has ≤ 5 items.
- [ ] **Skill** `.claude/skills/dispatch-alerts/SKILL.md` (frontmatter `name: dispatch-alerts`, `description:` "Send today's Stock Mover notifications through Fo (Wajo): email digest, area-manager calls/texts, sign-off calls. Use when asked to dispatch or send Stock Mover alerts."). Body = instructions to Claude:
  1. Read `STOCK_MOVER_API` (default `https://<render-url>` placeholder; fall back to `python scripts/dispatch_preview.py --run contracts/real_run.json` output if unreachable).
  2. Use the `wajo-fo` MCP tools (list them first; pick the tools for email, text and call). If the server isn't authenticated, stop and tell the user to run `/mcp` → `wajo-fo` → sign in.
  3. Recipients come from a local, git-ignored `.claude/skills/dispatch-alerts/recipients.json` (`{"merchandiser": {"email": ...}, "AM-02": {"name": ..., "phone": ..., "email": ...}, ...}`) — never hard-code numbers; include `recipients.example.json` with placeholders. For the demo, the user maps one AM to their own phone.
  4. Email the digest to the merchandiser. For each AM with items: ask Fo to text (or call, if `--call`) with the AM message, max 5 items, in Hindi-friendly plain English. For each sign-off request: ask Fo to call the merchandiser, read the move, ask "approve or reject?", and on a clear answer POST `/api/groups/{group_id}/decision` with `by: "fo-call"`.
  5. After each send, POST `/api/notifications/log` `{channel: "fo", to, subject, ok}`.
  6. Report a table of what was sent.
- [ ] Add `.claude/skills/dispatch-alerts/recipients.json` to `.gitignore` — **ask S0 (via the user) to add that line** since `.gitignore` is S0's; until then don't create the real file inside the repo, create it but don't `git add` it.
- [ ] Commit + push; tell the user: "dispatch-alerts ready — run `/mcp` to sign in to wajo-fo, fill recipients.json, then say 'dispatch today's Stock Mover alerts'". If you can, do one real Fo test (text to the user's own number) and report it.
