"""APScheduler entry point — runs the daily refresh and pushes to GitHub.

This is the Docker / in-container path (docker-compose up runs this).
For ad-hoc / dev runs, prefer `bash pipeline/refresh.sh` which uses git
push instead of the REST API.

Schedule: daily at 09:00 UTC (~05:00 EST). Also runs once on startup so a
fresh container deploys immediately push a payload.
"""
from __future__ import annotations

import logging
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from ..config.settings import (
    DAILY_HOUR,
    DAILY_MINUTE,
    DAILY_TIMEZONE,
    GITHUB_FILE_PATH,
    LOG_DIR,
)
from ..frontend_formatter import main as run_formatter
from ..sender.github_pusher import push_file

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
PAYLOAD = PROJECT_ROOT / "data" / "payload.json"

Path(LOG_DIR).mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(Path(LOG_DIR) / "pipeline.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("cron_runner")


def run_daily() -> None:
    """Collect → format → push. Logs failures but never raises."""
    logger.info("=== run_daily start ===")
    t0 = time.monotonic()
    try:
        run_formatter()
        if not PAYLOAD.exists():
            logger.error("payload.json was not produced; skipping push")
            return
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
        ok = push_file(PAYLOAD, GITHUB_FILE_PATH, f"data: refresh payload {ts}")
        logger.info("push ok=%s", ok)
    except Exception:
        logger.error("run_daily FAILED:\n%s", traceback.format_exc())
    logger.info("=== run_daily done in %.1fs ===", time.monotonic() - t0)


def main() -> None:
    scheduler = BlockingScheduler(timezone="UTC")
    scheduler.add_job(
        run_daily,
        CronTrigger(hour=DAILY_HOUR, minute=DAILY_MINUTE, timezone=DAILY_TIMEZONE),
        id="store_ops_daily",
        name="store-ops daily refresh",
        misfire_grace_time=3600,
    )
    logger.info(
        "scheduler started; daily refresh at %02d:%02d %s",
        DAILY_HOUR, DAILY_MINUTE, DAILY_TIMEZONE,
    )
    run_daily()  # immediate first run on container startup
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("scheduler stopped")


if __name__ == "__main__":
    main()
