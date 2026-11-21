"""Engine entry point. Owned by S0 (orchestration only — logic lives in the stage modules).

CLI:   python -m engine.run [--trigger manual|schedule|github] [--no-strict] [--out outputs]
Code:  from engine.run import run_engine; run = run_engine(trigger="schedule")
Writes outputs/latest.json and outputs/runs/<run_id>.json (contract C2).
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from engine import config as C
from engine.data import load_data
from engine.interfaces import build_features, find_flags, generate_moves, validate


class ValidationFailed(RuntimeError):
    def __init__(self, run: dict):
        super().__init__(f"{len(run['validation']['violations'])} rule violation(s)")
        self.run = run


def _clean(o):
    """Make numpy / pandas / inf values JSON-safe (inf & NaN -> None, Timestamp -> YYYY-MM-DD)."""
    if isinstance(o, dict):
        return {k: _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple, set)):
        return [_clean(v) for v in o]
    if isinstance(o, (pd.Timestamp, datetime)):
        return o.strftime("%Y-%m-%d")
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating, float)):
        f = float(o)
        return None if (math.isnan(f) or math.isinf(f)) else round(f, 3)
    if isinstance(o, np.bool_):
        return bool(o)
    if o is pd.NaT:
        return None
    return o


def _summary(groups: list[dict], stores_touched: set) -> dict:
    by_type = {t: sum(1 for g in groups if g["type"] == t) for t in C.MOVE_TYPES}
    return {
        "n_groups": len(groups),
        "n_moves": sum(len(g.get("lines", [])) for g in groups),
        "units": sum(g["qty"] for g in groups),
        "mrp_value": sum(g["mrp_value"] for g in groups),
        "revenue_protected": sum(g.get("revenue_at_risk", 0) for g in groups if g["type"] != "PULL_BACK"),
        "needs_approval": sum(1 for g in groups if g.get("needs_approval")),
        "by_type": by_type,
        "stores_touched": len(stores_touched),
    }


def run_engine(trigger: str = "manual", strict: bool = True, out_dir: Path = C.OUT_DIR,
               data_dir: Path = C.DATA_DIR) -> dict:
    started = datetime.now(timezone.utc)
    data = load_data(data_dir)
    feats = build_features(data)
    moves = generate_moves(data, feats)
    groups, problems = moves["groups"], moves["problems"]
    flags = find_flags(data, feats)
    validation = validate(data, feats, groups)

    touched = {g["from"] for g in groups} | {g["to"] for g in groups}
    touched.discard(C.WH_ID)
    run = _clean({
        "run_id": started.strftime("%Y%m%dT%H%M%SZ"),
        "as_of": data.as_of,
        "generated_at": started.isoformat(timespec="seconds"),
        "trigger": trigger,
        "summary": _summary(groups, touched),
        "problems": problems,
        "groups": sorted(groups, key=lambda g: -g.get("priority", 0)),
        "flags": flags,
        "stores": feats.store_pos.to_dict("records"),
        "validation": validation,
    })

    if strict and not run["validation"]["passed"]:
        raise ValidationFailed(run)

    out_dir = Path(out_dir)
    (out_dir / "runs").mkdir(parents=True, exist_ok=True)
    text = json.dumps(run, indent=1, ensure_ascii=False)
    (out_dir / "runs" / f"{run['run_id']}.json").write_text(text, encoding="utf-8")
    (out_dir / "latest.json").write_text(text, encoding="utf-8")
    return run


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--trigger", default="manual")
    ap.add_argument("--no-strict", action="store_true")
    ap.add_argument("--out", default=str(C.OUT_DIR))
    a = ap.parse_args(argv)
    try:
        run = run_engine(trigger=a.trigger, strict=not a.no_strict, out_dir=Path(a.out))
    except ValidationFailed as e:
        print(f"RUN BLOCKED: {e}", file=sys.stderr)
        for v in e.run["validation"]["violations"][:20]:
            print("  ", v, file=sys.stderr)
        return 2
    s = run["summary"]
    print(f"run {run['run_id']} as_of {run['as_of']}: {s['n_groups']} groups, {s['units']} units, "
          f"{len(run['flags'])} flags, validation passed={run['validation']['passed']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
