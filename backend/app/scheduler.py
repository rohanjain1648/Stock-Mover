"""Daily 07:00 IST engine run + notifications (APScheduler, in-process).

Render's free tier sleeps when idle, so the GitHub Actions cron (POST /api/runs) is the
belt to this scheduler's braces.
"""
from __future__ import annotations

import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from backend.app import notify, runs

log = logging.getLogger("stock_mover.scheduler")


def daily_job() -> None:
    try:
        run = runs.trigger_run("schedule")
    except runs.RunInProgress:
        log.info("07:00 run skipped: a run is already in progress")
        return
    except runs.ValidationFailed as e:
        log.warning("07:00 run blocked by validator (%s); previous run stays live", e)
        return
    except Exception:  # noqa: BLE001 - keep the scheduler alive
        log.exception("07:00 run failed")
        return
    try:
        notify.send_all(run)
    except Exception:  # noqa: BLE001
        log.exception("07:00 notifications failed")


def start(app) -> BackgroundScheduler:
    sched = BackgroundScheduler(timezone=notify.IST)
    sched.add_job(daily_job, CronTrigger(hour=7, minute=0, timezone=notify.IST), id="daily-run",
                  coalesce=True, max_instances=1, misfire_grace_time=3600, replace_existing=True)
    sched.start()
    app.state.scheduler = sched
    log.info("scheduler started: daily-run at 07:00 Asia/Kolkata")
    return sched


def stop(app) -> None:
    sched = getattr(app.state, "scheduler", None)
    if sched is not None:
        sched.shutdown(wait=False)
        app.state.scheduler = None
