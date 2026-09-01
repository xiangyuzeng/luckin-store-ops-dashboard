"""
Credential and connection settings.

Credentials are pulled from AWS Secrets Manager. The secret name is **always**
read from `MYSQL_SECRET_NAME` — there is no hardcoded default. This keeps the
real secret identifier out of the codebase and forces the runner to set it
explicitly per environment.

Expected secret payload (JSON) — matches the schema used by the canonical
`collector/mysql` secret that luckin-ops-dashboard and luckin-efficiency-dashboard
already consume:

    {
      "host":     "...",
      "port":     3306,
      "username": "...",
      "password": "...",
      "dbname":   "luckyus_iluckyhealth"   // optional (default DB; collectors override)
    }
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
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

# ── Daily cron schedule (consumed by pipeline/scheduler/cron_runner.py) ──
# 02:30 US/Eastern = 06:30 UTC. It used to be 01:00 ET = 05:00 UTC, which put
# this refresh inside the nightly batch window on aws-luckyus-salesorder-rw:
# CloudWatch shows CPU 24.2% against an 8~11% baseline and ReadLatency 0.9~2.5
# → 4.2 ms at 05:00, with the 02:00 UTC finance reconciliation peaking higher
# still (LCNA-DBA-SQL-2026-0901-B, action B-05). Moving off the hour costs the
# board 1.5 h of freshness on data that is already a day old.
DAILY_TIMEZONE = os.environ.get("DAILY_TIMEZONE", "US/Eastern")
DAILY_HOUR = int(os.environ.get("DAILY_HOUR", "2"))
DAILY_MINUTE = int(os.environ.get("DAILY_MINUTE", "30"))

# ── hourlyCupAchieve target ─────────────────────────────────────────
# Theoretical equivalent-cups-per-hour benchmark used as the denominator
# for hourlyCupAchieve = perfHourlyCups / THEORETICAL_HOURLY_CUPS.
# 30 杯/小时 is the initial placeholder — China HQ may publish a
# different number per shop tier; revisit once we have that input.
THEORETICAL_HOURLY_CUPS = float(os.environ.get("THEORETICAL_HOURLY_CUPS", "30"))


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
    # The canonical secret schema uses `username` and `dbname`; older / hand-rolled
    # secrets sometimes use `user` and `database`, so accept both.
    raw = _read_secret()
    user = raw.get("username") or raw.get("user")
    if not user:
        raise RuntimeError("Secret has neither 'username' nor 'user' key")
    return DbCredentials(
        host=raw["host"],
        port=int(raw.get("port", 3306)),
        user=user,
        password=raw["password"],
        database=raw.get("dbname") or raw.get("database") or "luckyus_iluckyhealth",
    )


# Per-database host resolution. The four databases the collectors query
# live on four separate RDS instances in production; the AWS Secrets Manager
# secret only carries one host (whichever instance was originally registered),
# so we need to redirect each connect() call to the right endpoint.
#
# Resolution order:
#   1. Per-database env var (e.g. OPSHOP_HOST=...)               — explicit override
#   2. RDS instance ID from rds_instances.json + boto3 lookup    — default
#   3. The host field on the AWS secret                          — fallback
#
# Instance IDs live in pipeline/config/rds_instances.json so the data (DB →
# instance mapping) is decoupled from the resolver logic.
_RDS_INSTANCES_FILE = Path(__file__).resolve().parent / "rds_instances.json"
_DB_HOST_ENV_KEYS: dict[str, str] = {
    "luckyus_opshop":           "OPSHOP_HOST",
    "luckyus_sales_order":      "SALESORDER_HOST",
    "luckyus_scm_shopstock":    "SCM_SHOPSTOCK_HOST",
    "luckyus_iluckyhealth":     "ILUCKYHEALTH_HOST",
    "luckyus_opempefficiency":  "OPEMPEFFICIENCY_HOST",
    "luckyus_opqualitycontrol": "OPQUALITYCONTROL_HOST",
    "luckyus_scm_commodity":    "SCM_COMMODITY_HOST",
    "luckyus_scm_purchase":     "SCM_PURCHASE_HOST",
}

_db_to_instance_cache: dict[str, str] | None = None
_instance_to_endpoint_cache: dict[str, str] = {}


def _load_rds_instance_map() -> dict[str, str]:
    global _db_to_instance_cache
    if _db_to_instance_cache is None:
        with _RDS_INSTANCES_FILE.open(encoding="utf-8") as f:
            _db_to_instance_cache = json.load(f)
    return _db_to_instance_cache


def _rds_endpoint(instance_id: str) -> str:
    """Look up the live endpoint for an RDS instance ID. Cached per process."""
    if instance_id in _instance_to_endpoint_cache:
        return _instance_to_endpoint_cache[instance_id]
    import boto3  # lazy import
    rds = boto3.client("rds", region_name=DEFAULT_REGION)
    resp = rds.describe_db_instances(DBInstanceIdentifier=instance_id)
    endpoint = resp["DBInstances"][0]["Endpoint"]["Address"]
    _instance_to_endpoint_cache[instance_id] = endpoint
    return endpoint


def _resolve_host(database: str, secret_host: str) -> str:
    env_key = _DB_HOST_ENV_KEYS.get(database)
    if env_key:
        override = os.environ.get(env_key)
        if override:
            return override
    instance_id = _load_rds_instance_map().get(database)
    if instance_id:
        return _rds_endpoint(instance_id)
    return secret_host


def connect(database: str | None = None):
    """Return a pymysql connection. SELECT-only; the pipeline never writes."""
    import pymysql  # lazy import
    creds = load_credentials()
    target_db = database or creds.database
    host = _resolve_host(target_db, creds.host)
    return pymysql.connect(
        host=host,
        port=creds.port,
        user=creds.user,
        password=creds.password,
        database=target_db,
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
