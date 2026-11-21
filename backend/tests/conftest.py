import copy
import json
import os
from pathlib import Path

import pytest

os.environ.setdefault("RUN_TOKEN", "test-token")

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture()
def client(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    monkeypatch.setenv("STATE_DB", str(tmp_path / "state.db"))
    monkeypatch.setenv("DISABLE_SCHEDULER", "1")
    from backend.app.main import app
    with TestClient(app) as c:
        yield c
        t = getattr(app.state, "last_notify", None)
        if t is not None:
            t.join(10)


@pytest.fixture(autouse=True)
def no_smtp(monkeypatch):
    """Never send real mail from tests, whatever the developer's shell exports."""
    import os as _os
    for k in [k for k in _os.environ if k.startswith(("SMTP_", "AM_EMAIL_")) or k == "DIGEST_TO"]:
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("PUBLIC_APP_URL", "https://stock-mover.vercel.app/")


@pytest.fixture()
def db(tmp_path):
    from backend.app import store
    store.init_db(tmp_path / "state.db")
    return store


@pytest.fixture()
def real_run():
    """A passing run shaped like an engine result (sample with a real-looking id)."""
    run = json.loads((ROOT / "contracts" / "sample_run.json").read_text(encoding="utf-8"))
    run = copy.deepcopy(run)
    run["run_id"] = "20261121T013000Z"
    run["trigger"] = "schedule"
    return run
