"""Shared helpers: config loading, data loading, field-role access.

Every script goes through here so that the evidence/answer split is enforced
in one place. If a script needs an answer field, it must ask for it explicitly
via `answer_field()`, which makes the intent visible in code review.
"""
from __future__ import annotations

import glob
import json
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "config.yaml"
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        raise SystemExit("config.yaml missing — copy config.example.yaml and fill it in (Session 0).")
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


def evidence_field(cfg: dict, role: str) -> str:
    name = cfg["fields"]["evidence"].get(role, "")
    if not name:
        raise SystemExit(f"config.yaml: fields.evidence.{role} is not set.")
    return name


def answer_field(cfg: dict, role: str) -> str:
    """Explicit accessor for answer-half fields. Grep for this to audit who touches the answers."""
    name = cfg["fields"]["answer"].get(role, "")
    if not name:
        raise SystemExit(f"config.yaml: fields.answer.{role} is not set.")
    return name


def load_raw_frame() -> pd.DataFrame:
    """Load every JSON file under data/raw/ into one DataFrame.

    Assumes each file is either a list of case dicts or a dict with a list
    under some key. Adjust `_extract_records` once you've seen a real response.
    """
    files = sorted(glob.glob(str(RAW / "**" / "*.json"), recursive=True))
    if not files:
        raise SystemExit("No raw JSON under data/raw/. Run fetch.py first.")
    records = []
    for fp in files:
        with open(fp) as f:
            payload = json.load(f)
        records.extend(_extract_records(payload))
    df = pd.json_normalize(records)
    df.attrs["source_files"] = files
    return df


def _extract_records(payload) -> list[dict]:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for v in payload.values():
            if isinstance(v, list) and v and isinstance(v[0], dict):
                return v
    raise SystemExit("Could not find a list of case records in the payload — edit _extract_records().")


def apply_filters(df: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Post-2008, GA, closed. The GA and closed predicates depend on real field
    values you'll only know after Session 0 — edit the two TODO lines."""
    f = cfg["fields"]
    date_col = f["event_date"]
    df = df.copy()
    df["_event_year"] = pd.to_datetime(df[date_col], errors="coerce").dt.year
    df = df[df["_event_year"] >= cfg["filters"]["min_event_year"]]
    if cfg["filters"].get("closed_only"):
        # TODO Session 0: replace with the real closed/completed predicate
        df = df[df[f["status"]].astype(str).str.lower().str.contains("complet|final|closed", na=False)]
    if cfg["filters"].get("ga_only"):
        # TODO Session 0: filter to Part 91 / general aviation using whatever field encodes it
        pass
    return df


def stratified_sample(df: pd.DataFrame, by: str, n: int, seed: int = 7) -> pd.DataFrame:
    """Sample n rows with each category of `by` represented in proportion."""
    counts = df[by].value_counts(normalize=True)
    parts = []
    for cat, share in counts.items():
        k = max(1, round(share * n))
        parts.append(df[df[by] == cat].sample(min(k, (df[by] == cat).sum()), random_state=seed))
    return pd.concat(parts).sample(frac=1, random_state=seed).head(n)


def save_processed(df: pd.DataFrame, name: str) -> Path:
    PROCESSED.mkdir(parents=True, exist_ok=True)
    out = PROCESSED / f"{name}.parquet"
    df.to_parquet(out, index=False)
    return out
