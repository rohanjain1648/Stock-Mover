"""Stock Mover API (contract C3). Run from the repo root:

    uvicorn backend.app.main:app --reload --port 8000

Env: STATE_DB (default backend/state.db), DISABLE_SCHEDULER=1 (no 07:00 job, no boot run).
"""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from backend.app import runs, store

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("stock_mover.api")

DEFAULT_DB = Path(__file__).resolve().parents[1] / "state.db"


def _background_enabled() -> bool:
    return os.environ.get("DISABLE_SCHEDULER", "") not in ("1", "true", "yes")


@asynccontextmanager
async def lifespan(app: FastAPI):
    store.init_db(os.environ.get("STATE_DB") or DEFAULT_DB)
    if _background_enabled():
        # serve the stored run / sample immediately; refresh from the engine in the background
        runs.start_background_run("schedule")
    yield


app = FastAPI(title="Stock Mover API", version="1.0.0", lifespan=lifespan)


@app.get("/api/health")
def health():
    run = runs.current_run()
    return {"status": "ok", "latest_run_id": run["run_id"], "data_as_of": run["as_of"],
            "is_sample": run["is_sample"], "run_in_progress": runs.is_running()}


@app.get("/api/runs/latest")
def runs_latest():
    return runs.with_decisions(runs.current_run())


@app.get("/api/runs")
def runs_history():
    rows = store.list_runs()
    if not rows:
        s = runs.current_run()
        rows = [{"run_id": s["run_id"], "generated_at": s["generated_at"], "trigger": s["trigger"],
                 "n_groups": len(s["groups"]), "passed": True, "is_sample": True}]
    return rows


@app.get("/api/stores")
def stores():
    run = runs.current_run()
    out = []
    for s in run["stores"]:
        sid = s["store_id"]
        inbound = [g for g in run["groups"] if g["to"] == sid]
        outbound = [g for g in run["groups"] if g["from"] == sid]
        out.append({**s,
                    "inbound_units": sum(g["qty"] for g in inbound),
                    "outbound_units": sum(g["qty"] for g in outbound),
                    "group_ids": [g["group_id"] for g in run["groups"] if sid in (g["from"], g["to"])]})
    return out
