"""
exploration.ingest
==================

Pulls raw QuFoods batch files, either from the live `qufoods-raw` S3
bucket or from a local folder of sample batches (for offline development
before AWS credentials are available, or for fast unit testing).

This builds directly on the functions given in `qufoods_starter_notebook.ipynb`
(`list_recent_keys`, `load_batches`) rather than reinventing them — Lambda's
ingestion logic (Emmanuel's side) should end up looking very similar to this,
since it answers the same question: "which files are new since the last run?"

Two ways to get records, picked automatically based on what's configured:

1. Live S3   — set QUFOODS_USE_S3=true and have valid AWS creds. Pulls real
   batches partitioned by year=YYYY/month=MM/day=DD/.
2. Local      — default mode. Reads every .json batch file out of
   `data/sample_batches/`. Lets the rest of the exploration pipeline (and
   anyone else on the team) run and test against realistic data with zero
   AWS dependency.

IMPORTANT — the brief vs. the starter notebook disagree on access method:
the brief says files are fetchable via public URL with no AWS credentials;
the starter notebook's `list_recent_keys`/`load_batches` require
`s3:ListBucket` + `s3:GetObject` via boto3. This module defaults to the
boto3 path (matches the starter notebook and the SOW's IAM assumption) but
keeps the public-URL path available via `load_batch_from_url` in case that
discrepancy gets resolved in the team's favor. Flagged in the data quality
log — see DATA_QUALITY_LOG.md, Finding #6.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

import pandas as pd
import requests

logger = logging.getLogger(__name__)

DEFAULT_BUCKET = "qufoods-raw"
DEFAULT_REGION = "us-east-1"
DEFAULT_LOOKBACK_MINUTES = 1440  # 24h — wide enough for exploration; Lambda will use 5


@dataclass(frozen=True)
class IngestResult:
    """Container for what came back from a pull, plus light provenance.

    Keeping provenance (which files, how many records) attached to the
    DataFrame's origin matters once you're profiling data quality — "BR-06
    has a 40% null rate" is a different finding if it's from 3 files vs 300.
    """

    records: list[dict]
    source_keys: list[str]
    pulled_at: datetime

    @property
    def raw_df(self) -> pd.DataFrame:
        return pd.DataFrame(self.records)

    def __len__(self) -> int:
        return len(self.records)


# ---------------------------------------------------------------------------
# Live S3 path — same approach as the starter notebook, factored for reuse.
# ---------------------------------------------------------------------------

def list_recent_keys(
    bucket: str = DEFAULT_BUCKET,
    minutes: int = DEFAULT_LOOKBACK_MINUTES,
    profile: str | None = None,
) -> list[str]:
    """List raw-bucket keys modified within the last `minutes`.

    Identical logic to the starter notebook's function of the same name.
    Kept here so Lambda's discovery logic (5-minute window in production)
    and exploration's discovery logic (24h+ window for profiling) share one
    implementation instead of drifting apart.
    """
    import boto3  # imported lazily so this module loads without boto3 installed

    session = boto3.Session(profile_name=profile) if profile else boto3.Session()
    s3 = session.client("s3")
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(minutes=minutes)

    # Build the set of day-partitions that could fall inside the window —
    # matters at midnight UTC boundaries where the window spans two prefixes.
    prefixes: set[str] = set()
    cursor = cutoff
    while cursor <= now:
        prefixes.add(cursor.strftime("year=%Y/month=%m/day=%d/"))
        cursor += timedelta(days=1)
    prefixes.add(now.strftime("year=%Y/month=%m/day=%d/"))

    keys: list[str] = []
    paginator = s3.get_paginator("list_objects_v2")
    for prefix in prefixes:
        for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
            for obj in page.get("Contents", []):
                if obj["LastModified"] >= cutoff:
                    keys.append(obj["Key"])
    return sorted(keys)


def load_batches(
    bucket: str = DEFAULT_BUCKET,
    keys: Iterable[str] = (),
    profile: str | None = None,
) -> list[dict]:
    """Download each key and flatten its `records` into one list."""
    import boto3

    session = boto3.Session(profile_name=profile) if profile else boto3.Session()
    s3 = session.client("s3")
    records: list[dict] = []
    for key in keys:
        body = s3.get_object(Bucket=bucket, Key=key)["Body"].read()
        batch = json.loads(body)
        records.extend(batch["records"])
    return records


def pull_from_s3(
    bucket: str = DEFAULT_BUCKET,
    minutes: int = DEFAULT_LOOKBACK_MINUTES,
    profile: str | None = None,
) -> IngestResult:
    """Full live pull: discover keys, then load them."""
    keys = list_recent_keys(bucket, minutes, profile)
    logger.info("found %d batch file(s) in the last %d minutes", len(keys), minutes)
    records = load_batches(bucket, keys, profile)
    return IngestResult(records=records, source_keys=keys, pulled_at=datetime.now(timezone.utc))


def load_batch_from_url(url: str) -> list[dict]:
    """Fallback path matching the brief's stated public-URL access method.

    Use only if the team confirms credential-less access is actually how
    this is meant to work (see the IAM/public-URL discrepancy noted in the
    module docstring). Not used by default.
    """
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    batch = response.json()
    return batch["records"]


# ---------------------------------------------------------------------------
# Local path — same shape of result, reading from disk instead of S3.
# This is what makes the exploration code runnable today, before AWS
# access is confirmed, and what makes the unit tests deterministic.
# ---------------------------------------------------------------------------

def pull_from_local(sample_dir: str | Path) -> IngestResult:
    """Read every `.json` batch file in `sample_dir` and flatten records.

    `sample_dir` defaults (via the CLI / notebook) to
    `exploration/data/sample_batches/` which ships with one real batch
    pulled from the brief's example URL. Drop in more `.json` batch files
    here — same `{"batch_id", "ingested_at", "records": [...]}` shape — and
    every downstream profiling step scales with zero code changes.
    """
    sample_dir = Path(sample_dir)
    paths = sorted(sample_dir.glob("*.json"))
    if not paths:
        raise FileNotFoundError(
            f"No .json batch files found in {sample_dir}. "
            "Add at least one batch file matching the qufoods-raw format."
        )

    records: list[dict] = []
    for path in paths:
        batch = json.loads(path.read_text())
        records.extend(batch.get("records", []))

    logger.info("loaded %d record(s) from %d local batch file(s)", len(records), len(paths))
    return IngestResult(
        records=records,
        source_keys=[str(p) for p in paths],
        pulled_at=datetime.now(timezone.utc),
    )


# ---------------------------------------------------------------------------
# Unified entry point — this is what notebooks / scripts should call.
# ---------------------------------------------------------------------------

def pull_batches(
    use_s3: bool = False,
    bucket: str = DEFAULT_BUCKET,
    minutes: int = DEFAULT_LOOKBACK_MINUTES,
    profile: str | None = None,
    sample_dir: str | Path = "data/sample_batches",
) -> IngestResult:
    """Single entry point: live S3 if `use_s3=True`, local sample files otherwise.

    This is the only function most exploration code should call directly.
    Switching from local dev to live data later is a one-line change
    (`use_s3=True`), not a rewrite.
    """
    if use_s3:
        return pull_from_s3(bucket=bucket, minutes=minutes, profile=profile)
    return pull_from_local(sample_dir)
