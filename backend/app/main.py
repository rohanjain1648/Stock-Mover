"""Stock Mover API (contract C3). Run from the repo root:

    uvicorn backend.app.main:app --reload --port 8000

Env: STATE_DB (default backend/state.db), DISABLE_SCHEDULER=1 (no 07:00 job, no boot run).
"""
from __future__ import annotations

import csv
import hmac
import io
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, Header, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from backend.app import runs, store

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("stock_mover.api")

DEFAULT_DB = Path(__file__).resolve().parents[1] / "state.db"


LOCAL_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:4173"]
EXPORT_COLS = ["group_id", "type", "from", "to", "sku_id", "size", "qty", "ship_on", "arrives_on",
               "mrp_value_line", "explanation", "decision"]


def cors_origins() -> list[str]:
    """FRONTEND_ORIGIN (comma-separated, or '*') plus the Vite dev/preview origins."""
    raw = os.environ.get("FRONTEND_ORIGIN", "").strip()
    if raw == "*":
        return ["*"]
    extra = [o.strip().rstrip("/") for o in raw.split(",") if o.strip()]
    return list(dict.fromkeys(extra + LOCAL_ORIGINS))


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
app.add_middleware(CORSMiddleware, allow_origins=cors_origins(), allow_credentials=False,
                   allow_methods=["*"], allow_headers=["*"])


class DecisionIn(BaseModel):
    decision: Literal["approve", "reject"]
    note: str | None = None
    by: str | None = None


class BatchDecisionIn(DecisionIn):
    group_ids: list[str] = Field(default_factory=list)


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


@app.post("/api/groups/decision")
def decide_batch(body: BatchDecisionIn):
    run = runs.current_run()
    known = {g["group_id"] for g in run["groups"]}
    ids = [gid for gid in dict.fromkeys(body.group_ids) if gid in known]
    for gid in ids:
        store.set_decision(run["run_id"], gid, body.decision, body.note, body.by)
    return {"updated": len(ids)}


@app.post("/api/groups/{group_id}/decision")
def decide(group_id: str, body: DecisionIn):
    run = runs.current_run()
    if group_id not in {g["group_id"] for g in run["groups"]}:
        raise HTTPException(404, f"group {group_id} not in run {run['run_id']}")
    store.set_decision(run["run_id"], group_id, body.decision, body.note, body.by)
    return {"group_id": group_id, "decision": body.decision}


@app.get("/api/export.csv")
def export_csv(status: Literal["approved", "rejected", "all"] = "approved"):
    run = runs.with_decisions(runs.current_run())
    want = {"approved": {"approve"}, "rejected": {"reject"}, "all": {"approve", "reject", None}}[status]
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=EXPORT_COLS)
    w.writeheader()
    for g in run["groups"]:
        if g["decision"] not in want:
            continue
        for ln in g["lines"]:
            w.writerow({"group_id": g["group_id"], "type": g["type"], "from": g["from"], "to": g["to"],
                        "sku_id": ln["sku_id"], "size": ln["size"], "qty": ln["qty"],
                        "ship_on": g["ship_on"], "arrives_on": g["arrives_on"],
                        # MRP is uniform across sizes of a style, so the pro-rata share is exact
                        "mrp_value_line": round(g["mrp_value"] * ln["qty"] / g["qty"]) if g["qty"] else 0,
                        "explanation": g["explanation"], "decision": g["decision"] or ""})
    name = f"stock-mover-{status}-{run['run_id']}.csv"
    return Response(buf.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{name}"'})


@app.post("/api/runs")
def trigger(trigger: Literal["github", "manual", "schedule"] = Query("manual"),
            x_run_token: str | None = Header(None)):
    expected = os.environ.get("RUN_TOKEN", "")
    if not expected or not x_run_token or not hmac.compare_digest(x_run_token, expected):
        raise HTTPException(401, "bad or missing X-Run-Token")
    try:
        run = runs.trigger_run(trigger)       # sync endpoint -> runs in FastAPI's threadpool
    except runs.RunInProgress:
        raise HTTPException(409, "run in progress")
    except runs.ValidationFailed as e:
        v = e.run["validation"]
        raise HTTPException(409, {"error": "validation failed; previous run stays live",
                                  "run_id": e.run["run_id"], "n_violations": len(v["violations"]),
                                  "violations": v["violations"][:5]})
    return {"run_id": run["run_id"], "summary": run["summary"], "passed": run["validation"]["passed"]}
