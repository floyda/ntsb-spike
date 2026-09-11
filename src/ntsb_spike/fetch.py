"""Session 0 — pull a date range from the official NTSB Enterprise API into data/raw/.

Usage:
    python -m ntsb_spike.fetch 2022-03-01 2022-03-31

API: GET {base_url}/api/Common/v2/GetCasesByDateRange/ (spec: public.yaml from the
developer portal). Params: startDate, endDate (YYYY-MM-DD), mode=aviation, and a
continuation `marker` for paging (response fields: pageSize, hasMore, nextMarker,
data[]). Auth: Ocp-Apim-Subscription-Key header — the key is read from the
NTSB_API_KEY environment variable only and is never stored in the repo.

Each page's response is saved verbatim (page_NN.json); the concatenated data[]
lists are written 1:1 as cases_{start}_{end}.json for load_raw_frame().
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import date
from pathlib import Path

import requests

from .common import RAW, load_config


def _headers(cfg: dict) -> dict:
    key = os.environ.get("NTSB_API_KEY", "")
    if not key:
        raise SystemExit("No API key: export NTSB_API_KEY (kept in your password store, never in the repo).")
    return {
        "Ocp-Apim-Subscription-Key": key,
        "Cache-Control": "no-cache",
        "User-Agent": "ntsb-spike (personal research; contact in repo README)",
    }


def fetch_range(cfg: dict, start: str, end: str, out_dir: Path) -> list[dict]:
    api = cfg["api"]
    if not api["base_url"] or not api["endpoint"]:
        raise SystemExit("config.yaml api.base_url / api.endpoint not set — do Session 0 checklist first.")
    url = api["base_url"].rstrip("/") + "/" + api["endpoint"].strip("/")
    headers = _headers(cfg)
    delay = 60.0 / api["requests_per_minute"] if api.get("requests_per_minute") else 1.0

    records: list[dict] = []
    params = {"startDate": start, "endDate": end, "mode": "aviation"}
    page = 1
    while True:
        r = requests.get(url, params=params, headers=headers, timeout=120)
        r.raise_for_status()
        # Range-scoped name so two fetches on the same day can't overwrite
        # each other's verbatim pages.
        (out_dir / f"pages_{start}_{end}_p{page:02d}.json").write_bytes(r.content)
        payload = r.json() if r.content else {}
        batch = payload.get("data") or []
        records.extend(batch)
        print(
            f"page {page}: {len(batch)} records (hasMore={payload.get('hasMore')})",
            file=sys.stderr,
        )
        if not payload.get("hasMore") or not payload.get("nextMarker"):
            break
        params["marker"] = payload["nextMarker"]
        page += 1
        time.sleep(delay)
    return records


def save(records: list[dict], start: str, end: str, out_dir: Path) -> Path:
    out = out_dir / f"cases_{start}_{end}.json"
    with open(out, "w") as f:
        json.dump(records, f)
    return out


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    start, end = sys.argv[1], sys.argv[2]
    cfg = load_config()
    out_dir = RAW / f"fetched={date.today().isoformat()}"
    out_dir.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    recs = fetch_range(cfg, start, end, out_dir)
    out = save(recs, start, end, out_dir)
    print(f"{len(recs)} records → {out}  ({time.time() - t0:.1f}s)")


if __name__ == "__main__":
    main()
