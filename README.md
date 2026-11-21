# Stock Mover

**Right stock. Right store. Right size.** — Manyavar (Vedant Fashions) × Calcutta AI Club hackathon, Problem B.

Every morning Stock Mover reads Manyavar's sales and stock, finds stock in the wrong place, and produces a
ranked, ready-to-approve list of warehouse sends, store-to-store moves and pull-backs — each explained in one
line, checked against every rule, and delivered to the merchandiser and area managers.

- Design: [docs/superpowers/specs/2026-11-21-stock-mover-design.md](docs/superpowers/specs/2026-11-21-stock-mover-design.md)
- Contracts: [contracts/CONTRACTS.md](contracts/CONTRACTS.md)
- Session plans: [docs/plans/](docs/plans/) (S1 Demand · S2 Moves · S3 Rules & QA · S4 Backend · S5 Frontend)

## Run the engine
```bash
pip install -r requirements.txt
python -m engine.run              # strict: refuses to publish if any rule is broken
python -m engine.run --no-strict  # development
pytest -q
```
Output: `outputs/latest.json` (contract C2).

## Layout
```
engine/      data.py (load+clean) · velocity.py · position.py · moves.py · explain.py · rules.py · quality.py · run.py
backend/     FastAPI: runs, decisions, export, notifications, daily scheduler
frontend/    React + shadcn approval console
contracts/   frozen interfaces + sample_run.json
data/csv/    the 17 Manyavar tables (synthetic, as supplied)
```

## Parallel build (5 Claude sessions)
From PowerShell, once (after `main` has the scaffold):
```powershell
cd "D:\downloads\calcutta ai club stock mover\Stock-Mover"
git pull
foreach ($s in 1..5) { git worktree add "..\sm-s$s" -b "s$s" origin/main }
```
Then for each session: open a terminal in `..\sm-sN`, run `claude`, and paste:
> Read docs/plans/SN.md and execute it now. You are session SN.

Each session edits only the paths its plan owns and pushes with
`git fetch origin && git rebase origin/main && git push origin HEAD:main`.
