"""refresh.py — live data refresh as a background job.

Triggered by the team only (the /jobs/refresh route checks the password) or by the
optional nightly scheduler. Re-fetches the snapshot from the public WLO API, rebuilds
the data truth and loads it into memory. A concurrency guard (lock) prevents parallel
runs; start_scheduler() can drive a once-a-day run.
"""
import datetime
import logging
import threading
import time

import fetcher
import store
import truth

_JOB = {"status": "idle", "percent": 0, "message": "", "error": None,
        "startedAt": None, "finishedAt": None, "meta": None}
_JOB_LOCK = threading.Lock()


def _run_refresh():
    try:
        _JOB.update(status="running", percent=0, message="Start …", error=None,
                    startedAt=time.strftime("%Y-%m-%d %H:%M:%S"), finishedAt=None)
        fetcher.refresh_all(lambda p, m: _JOB.update(percent=int(p), message=m))
        _JOB.update(percent=96, message="Datenwahrheit neu bauen …")
        meta = truth.main()                 # builds data/truth.json
        store.load()                        # reload in memory
        _JOB.update(status="done", percent=100, message="Fertig.",
                    meta=meta, finishedAt=time.strftime("%Y-%m-%d %H:%M:%S"))
    except Exception:                        # noqa: BLE001
        # Log the full exception server-side, but NEVER surface its text on the public /jobs/latest
        # status (it could leak file paths, the repo host or upstream API error detail).
        logging.getLogger("refresh").exception("refresh job failed")
        _JOB.update(status="error", error="internal", message="Aktualisierung fehlgeschlagen.",
                    finishedAt=time.strftime("%Y-%m-%d %H:%M:%S"))


def start():
    # Concurrency guard: repeated clicks during a run are no-ops.
    with _JOB_LOCK:
        if _JOB["status"] == "running":
            return {"status": "running", "percent": _JOB["percent"], "message": _JOB["message"]}
        _JOB.update(status="running", percent=0, message="Start …", error=None,
                    startedAt=time.strftime("%Y-%m-%d %H:%M:%S"))
    threading.Thread(target=_run_refresh, daemon=True).start()
    return {"status": "started"}


def status():
    # Return a snapshot copy under the lock, so a caller (the public progress poll) never observes
    # the dict mid-update from the background thread.
    with _JOB_LOCK:
        return dict(_JOB)


def _seconds_until(hour):
    """Seconds from now to the next occurrence of `hour`:00 in local time."""
    now = datetime.datetime.now()
    target = now.replace(hour=hour, minute=0, second=0, microsecond=0)
    if target <= now:
        target += datetime.timedelta(days=1)
    return (target - now).total_seconds()


_SCHEDULER_STARTED = False


def start_scheduler(hour):
    """Start a daemon thread that triggers a refresh once a day at `hour`:00 (local
    time). No-op when hour is None (disabled). Idempotent: only one nightly thread even
    if called repeatedly (e.g. on a worker reload). Reuses the same concurrency-guarded
    job as the manual button, so a long-running refresh is never double-started."""
    global _SCHEDULER_STARTED
    if hour is None or _SCHEDULER_STARTED:
        return
    _SCHEDULER_STARTED = True

    def _loop():
        while True:
            time.sleep(_seconds_until(hour))
            start()
            time.sleep(61)   # avoid re-triggering within the same minute

    threading.Thread(target=_loop, daemon=True, name="nightly-refresh").start()
