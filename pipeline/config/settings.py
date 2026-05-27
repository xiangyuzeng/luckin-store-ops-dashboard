"""
Credential and connection settings.

Credentials are pulled from AWS Secrets Manager. The secret name is **always**
read from `MYSQL_SECRET_NAME` — there is no hardcoded default. This keeps the
real secret identifier out of the codebase and forces the runner to set it
explicitly per environment.

Expected secret payload (JSON):

    {
      "host":     "...",
      "port":     3306,
      "user":     "...",
      "password": "...",
      "database": "luckyus_iluckyhealth"   // (default DB; collectors override)
    }
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

DEFAULT_REGION = os.environ.get("AWS_REGION", "us-east-1")
TENANT = os.environ.get("LUCKIN_TENANT", "LKUS")
US_EASTERN_SQL = "CONVERT_TZ({col}, 'UTC', 'US/Eastern')"

# GitHub push config — consumed by pipeline/sender/github_pusher.py.
# Required when running the in-container scheduler; the legacy refresh.sh
# uses `git push` and ignores these.
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GITHUB_REPO = os.environ.get("GITHUB_REPO", "xiangyuzeng/luckin-store-ops-dashboard")
GITHUB_BRANCH = os.environ.get("GITHUB_BRANCH", "main")
GITHUB_FILE_PATH = os.environ.get("GITHUB_FILE_PATH", "data/payload.json")

# Where the scheduler writes its log file. Inside Docker this is mounted as a volume.
LOG_DIR = os.environ.get("LOG_DIR", "logs")


@dataclass(frozen=True)
class DbCredentials:
    host: str
    port: int
    user: str
    password: str
    database: str


def _read_secret() -> dict[str, Any]:
    secret_name = os.environ.get("MYSQL_SECRET_NAME")
    if not secret_name:
        raise RuntimeError(
            "MYSQL_SECRET_NAME is not set. The pipeline refuses to run without an explicit "
            "Secrets Manager secret name; set it in the environment or pass via CI secrets."
        )
    import boto3  # lazy import — settings.py stays importable in environments without boto3
    client = boto3.client("secretsmanager", region_name=DEFAULT_REGION)
    resp = client.get_secret_value(SecretId=secret_name)
    payload = resp.get("SecretString")
    if not payload:
        raise RuntimeError(f"Secret {secret_name} has no SecretString payload")
    return json.loads(payload)


def load_credentials() -> DbCredentials:
    # Path B (simpler): direct env vars. Set MYSQL_HOST to enable this branch.
    # Useful when the runtime host can't reach AWS Secrets Manager (or when
    # operators prefer not to grant IAM permissions to the pipeline).
    if os.environ.get("MYSQL_HOST"):
        return DbCredentials(
            host=os.environ["MYSQL_HOST"],
            port=int(os.environ.get("MYSQL_PORT", "3306")),
            user=os.environ["MYSQL_USER"],
            password=os.environ["MYSQL_PASSWORD"],
            database=os.environ.get("MYSQL_DATABASE", "luckyus_iluckyhealth"),
        )
    # Path A (default): AWS Secrets Manager via MYSQL_SECRET_NAME.
    raw = _read_secret()
    return DbCredentials(
        host=raw["host"],
        port=int(raw.get("port", 3306)),
        user=raw["user"],
        password=raw["password"],
        database=raw.get("database", "luckyus_iluckyhealth"),
    )


def connect(database: str | None = None):
    """Return a pymysql connection. SELECT-only; the pipeline never writes."""
    import pymysql  # lazy import
    creds = load_credentials()
    return pymysql.connect(
        host=creds.host,
        port=creds.port,
        user=creds.user,
        password=creds.password,
        database=database or creds.database,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,  # type: ignore[union-attr]
        autocommit=True,
        connect_timeout=15,
        read_timeout=120,
    )


def assert_read_only(sql: str) -> None:
    """Reject any SQL that contains a write keyword. Defense in depth: collectors
    only build SELECT statements, and this check fails fast if a future edit ever
    sneaks in a write."""
    lowered = sql.lower()
    for kw in (" insert ", " update ", " delete ", " drop ", " truncate ", " replace ", " alter ", " grant ", " revoke "):
        if kw in f" {lowered} ":
            raise RuntimeError(f"Write keyword detected in SQL: {kw.strip()}")
