"""Session 0 — pull a date range from the API into data/raw/, date-partitioned.

Usage:
    python -m ntsb_spike.fetch 2022-03-01 2022-03-31

The request shape is deliberately not hard-coded: fill config.yaml from the
NTSB docs first (see docs/session-0-checklist.md). If the API doesn't work,
use `--from-avall` after downloading avall.zip.
"""
from __future__ import annotations

import json
import sys
import time
from datetime import date
from pathlib import Path

import requests

from .common import RAW, load_config


def fetch_range(cfg: dict, start: str, end: str) -> list[dict]:
    api = cfg["api"]
    if not api["base_url"] or not api["endpoint"]:
        raise SystemExit("config.yaml api.base_url / api.endpoint not set — do Session 0 checklist first.")
    url = api["base_url"].rstrip("/") + "/" + api["endpoint"].lstrip("/")
    # TODO Session 0: set the real parameter names and pagination from the docs.
    params = {"startDate": start, "endDate": end}
    headers = {"User-Agent": "ntsb-spike (personal research; contact in repo README)"}
    records: list[dict] = []
    page = 1
    delay = 60.0 / api["requests_per_minute"] if api.get("requests_per_minute") else 1.0
    while True:
        r = requests.get(url, params={**params, "page": page}, headers=headers, timeout=60)
        r.raise_for_status()
        payload = r.json()
        # TODO Session 0: extract the list of cases and the next-page signal from `payload`.
        batch = payload if isinstance(payload, list) else next(
            (v for v in payload.values() if isinstance(v, list)), []
        )
        records.extend(batch)
        print(f"page {page}: {len(batch)} records (total {len(records)})", file=sys.stderr)
        if not batch or len(batch) < api.get("page_size", 1):
            break
        page += 1
        time.sleep(delay)
    return records


def save(records: list[dict], start: str, end: str) -> Path:
    out_dir = RAW / f"fetched={date.today().isoformat()}"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"cases_{start}_{end}.json"
    with open(out, "w") as f:
        json.dump(records, f)
    return out


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    start, end = sys.argv[1], sys.argv[2]
    cfg = load_config()
    t0 = time.time()
    recs = fetch_range(cfg, start, end)
    out = save(recs, start, end)
    print(f"{len(recs)} records → {out}  ({time.time() - t0:.1f}s)")


if __name__ == "__main__":
    main()
