"""GitHub Contents API pusher.

Uploads a local file to a GitHub repo path via REST (PUT). Used by the
in-container scheduler as the canonical push path; the legacy refresh.sh
uses `git push` instead and remains available for ad-hoc / dev runs.

Pattern lifted from luckin-ops-dashboard/pipeline/sender/github_pusher.py
(the dashboard that's been running end-to-end since April 2026).
"""
from __future__ import annotations

import base64
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

from ..config.settings import GITHUB_BRANCH, GITHUB_REPO, GITHUB_TOKEN

logger = logging.getLogger(__name__)

_API_BASE = "https://api.github.com"
_MAX_RETRIES = 3
_BACKOFF_BASE = 2


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _current_sha(repo_path: str) -> str | None:
    url = f"{_API_BASE}/repos/{GITHUB_REPO}/contents/{repo_path}"
    resp = requests.get(url, headers=_headers(), params={"ref": GITHUB_BRANCH}, timeout=15)
    if resp.status_code == 200:
        return resp.json().get("sha")
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return None


def push_file(local_path: Path, repo_path: str, message: str | None = None) -> bool:
    """Upload local_path to GITHUB_REPO at repo_path on GITHUB_BRANCH.

    Returns True on success. Retries 3x with exponential backoff on
    network errors or 5xx responses.
    """
    if not GITHUB_TOKEN:
        logger.error("GITHUB_TOKEN not set; refusing to push")
        return False
    if not GITHUB_REPO:
        logger.error("GITHUB_REPO not set; refusing to push")
        return False
    if not local_path.exists():
        logger.error("local file %s does not exist", local_path)
        return False

    content_bytes = local_path.read_bytes()
    encoded = base64.b64encode(content_bytes).decode("ascii")
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
    body = {
        "message": message or f"data: refresh {repo_path} {ts} UTC",
        "content": encoded,
        "branch": GITHUB_BRANCH,
    }
    sha = _current_sha(repo_path)
    if sha:
        body["sha"] = sha

    url = f"{_API_BASE}/repos/{GITHUB_REPO}/contents/{repo_path}"
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            resp = requests.put(url, headers=_headers(), json=body, timeout=60)
            if resp.status_code in (200, 201):
                logger.info(
                    "push OK %s → %s (attempt %d, %.1f KB)",
                    local_path.name, repo_path, attempt, len(content_bytes) / 1024,
                )
                return True
            logger.warning(
                "push HTTP %d (attempt %d): %s",
                resp.status_code, attempt, resp.text[:300],
            )
        except requests.RequestException as exc:
            logger.warning("push network error (attempt %d): %s", attempt, exc)

        if attempt < _MAX_RETRIES:
            time.sleep(_BACKOFF_BASE ** attempt)

    logger.error("push FAILED after %d attempts: %s → %s", _MAX_RETRIES, local_path, repo_path)
    return False
