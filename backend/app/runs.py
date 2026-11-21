"""Engine runs: keep the last *passing* run live, fall back to the bundled sample.

`trigger_run` runs `engine.run.run_engine` in-process (strict: a run with rule breaks
raises `ValidationFailed`, is recorded in history, and is never served).
"""
from __future__ import annotations

import copy
import json
import logging
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:          # the engine package lives at the repo root
    sys.path.insert(0, str(ROOT))

from engine.run import ValidationFailed, run_engine  # noqa: E402

from backend.app import store  # noqa: E402

log = logging.getLogger("stock_mover.runs")

SAMPLE_PATH = ROOT / "contracts" / "sample_run.json"
_LOCK = threading.Lock()
_sample: dict | None = None

__all__ = ["RunInProgress", "ValidationFailed", "current_run", "trigger_run", "with_decisions",
           "is_running", "start_background_run"]


class RunInProgress(RuntimeError):
    pass


def _sample_run() -> dict:
    global _sample
    if _sample is None:
        _sample = json.loads(SAMPLE_PATH.read_text(encoding="utf-8"))
        _sample["is_sample"] = True
    return copy.deepcopy(_sample)


def current_run() -> dict:
    """Latest passing run from the store, else the sample with is_sample=True."""
    run = store.latest_run()
    if run is None:
        return _sample_run()
    run["is_sample"] = False
    return run


def with_decisions(run: dict) -> dict:
    """Copy of `run` where every group carries `decision` / `decision_note` (null if undecided)."""
    dec = store.decisions(run["run_id"])
    out = dict(run)
    out["groups"] = [{**g, "decision": dec.get(g["group_id"], {}).get("decision"),
                      "decision_note": dec.get(g["group_id"], {}).get("note")} for g in run["groups"]]
    return out


def _same_move(a: dict, b: dict) -> bool:
    return all(a.get(k) == b.get(k) for k in ("style_id", "from", "to", "qty"))


def _carry_decisions(prev: dict, new: dict) -> int:
    """Copy decisions from the previous live run for groups that are the same move."""
    prev_dec = store.decisions(prev["run_id"])
    prev_groups = {g["group_id"]: g for g in prev["groups"]}
    n = 0
    for g in new["groups"]:
        p = prev_groups.get(g["group_id"])
        d = prev_dec.get(g["group_id"])
        if p and d and _same_move(p, g):
            store.set_decision(new["run_id"], g["group_id"], d["decision"], d["note"], d["by"])
            n += 1
    return n


def is_running() -> bool:
    return _LOCK.locked()


def trigger_run(trigger: str) -> dict:
    """Run the engine now. Raises RunInProgress if one is already running, ValidationFailed on rule breaks."""
    if not _LOCK.acquire(blocking=False):
        raise RunInProgress("run in progress")
    try:
        prev = current_run()
        try:
            run = run_engine(trigger=trigger, strict=True)
        except ValidationFailed as e:
            store.save_run(e.run)          # history shows the blocked attempt; live run unchanged
            raise
        carried = _carry_decisions(prev, run)
        store.save_run(run)
        log.info("run %s stored (%d groups, %d decisions carried)", run["run_id"], len(run["groups"]), carried)
        return run
    finally:
        _LOCK.release()


def start_background_run(trigger: str, then=None) -> threading.Thread:
    """Fire-and-forget engine run (used at boot so startup never waits on the engine)."""
    def work():
        try:
            run = trigger_run(trigger)
            if then is not None:
                then(run)
        except RunInProgress:
            log.info("background run skipped: run in progress")
        except ValidationFailed as e:
            log.warning("background run blocked by validator: %s", e)
        except Exception:  # noqa: BLE001 - a boot-time failure must not kill the API
            log.exception("background run failed")

    t = threading.Thread(target=work, name=f"engine-{trigger}", daemon=True)
    t.start()
    return t
