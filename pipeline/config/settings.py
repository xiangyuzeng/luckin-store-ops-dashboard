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
