"""Shared helpers: config loading, data loading, field-role access.

Every script goes through here so that the evidence/answer split is enforced
in one place. If a script needs an answer field, it must ask for it explicitly
via `answer_field()`, which makes the intent visible in code review.
"""
from __future__ import annotations

import glob
import json
import re
import sys
from pathlib import Path
from typing import Any

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


# Column names produced by the derived-field builders below rather than by
# resolving a raw JSON path. Configured field names that happen to match one of
# these are already satisfied once the derived columns are built — resolving
# them again as a literal path would just overwrite the real values with None.
DERIVED_COLUMNS = {
    "derived.eventCodes",
    "derived.findingCodes",
    "derived.pilotTotalHours",
    "derived.pilotHoursInMakeModel",
    "derived.far",
    "derived.phaseOfFlight",
}

# A path segment is a bare name or a name followed by a single [IDX] index,
# e.g. "aircrafts" or "aircrafts[0]".
_PATH_SEGMENT = re.compile(r"^([A-Za-z0-9_]+)(?:\[(\d+)\])?$")


def resolve_path(record: dict, path: str) -> Any:
    """Resolve a dotted JSON-path-like string against a nested case record.

    Segments look like `name` or `name[IDX]` (e.g.
    "aircrafts[0].ownerOperators[0].regulationFlightConductedUnder"). Returns
    None as soon as any hop is missing, the wrong type, or the index is out
    of range, instead of raising.
    """
    current: Any = record
    for segment in path.split("."):
        m = _PATH_SEGMENT.match(segment)
        if not m:
            return None
        key, idx = m.group(1), m.group(2)
        if not isinstance(current, dict) or key not in current:
            return None
        current = current[key]
        if idx is not None:
            if not isinstance(current, list):
                return None
            i = int(idx)
            if i >= len(current):
                return None
            current = current[i]
    return current


def _first_aircraft(record: dict) -> dict | None:
    """Return aircrafts[0] by convention, or None if there isn't one."""
    aircrafts = record.get("aircrafts")
    if not isinstance(aircrafts, list) or not aircrafts:
        return None
    return aircrafts[0]


def _event_codes(record: dict) -> list[str] | None:
    """Defining event first, then the rest ordered by sequenceNumber."""
    aircraft = _first_aircraft(record)
    if aircraft is None:
        return None
    events = aircraft.get("events")
    if not isinstance(events, list) or not events:
        return None
    defining = [e for e in events if e.get("isDefiningEvent")]
    rest = sorted((e for e in events if not e.get("isDefiningEvent")), key=lambda e: e.get("sequenceNumber") or 0)
    return [e["eventCode"] for e in (defining + rest) if e.get("eventCode") is not None]


def _phase_of_flight(record: dict) -> str | None:
    """cicttPhaseSOEGroup of the defining event (fallback: first event by sequence).

    Session 4 decision (Andy, 2026-09-11): phase is observable before any verdict,
    so it counts as evidence even though the value rides on the NTSB's coded
    defining event. Session 6 ablation will measure what it smuggles in.
    """
    aircraft = _first_aircraft(record)
    if aircraft is None:
        return None
    events = aircraft.get("events")
    if not isinstance(events, list) or not events:
        return None
    defining = [e for e in events if e.get("isDefiningEvent")]
    ordered = defining or sorted(events, key=lambda e: e.get("sequenceNumber") or 0)
    return ordered[0].get("cicttPhaseSOEGroup")


def _finding_codes(record: dict) -> list[str] | None:
    """findingCode strings ordered by findingNumber."""
    aircraft = _first_aircraft(record)
    if aircraft is None:
        return None
    findings = aircraft.get("findings")
    if not isinstance(findings, list) or not findings:
        return None
    ordered = sorted(findings, key=lambda f: f.get("findingNumber") or 0)
    return [f["findingCode"] for f in ordered if f.get("findingCode") is not None]


def _pilot_flight_hours(record: dict, flight_time_craft: str) -> float | None:
    """flightHours from the first crew member's Total row for the given craft scope."""
    aircraft = _first_aircraft(record)
    if aircraft is None:
        return None
    crew = aircraft.get("crewAndOccupants")
    if not isinstance(crew, list) or not crew:
        return None
    matrix = crew[0].get("pilotsFlightTimeMatrix")
    if not isinstance(matrix, list):
        return None
    for row in matrix:
        if row.get("flightTimeType") == "Total" and row.get("flightTimeCraft") == flight_time_craft:
            return row.get("flightHours")
    return None


def _far(record: dict) -> Any:
    aircraft = _first_aircraft(record)
    if aircraft is None:
        return None
    owner_operators = aircraft.get("ownerOperators")
    if not isinstance(owner_operators, list) or not owner_operators:
        return None
    return owner_operators[0].get("regulationFlightConductedUnder")


def _configured_field_names(cfg: dict) -> list[str]:
    """Every non-empty field name configured under fields.id/event_date/... and
    fields.evidence.*/fields.answer.*, in config.yaml order."""
    names = []
    for key in ("id", "event_date", "probable_cause_date", "status"):
        name = cfg["fields"].get(key)
        if name:
            names.append(name)
    for role_group in ("evidence", "answer"):
        for name in cfg["fields"].get(role_group, {}).values():
            if name:
                names.append(name)
    return names


def load_raw_frame() -> pd.DataFrame:
    """Load every JSON file under data/raw/ into one flat DataFrame.

    Assumes each file is either a list of case dicts or a dict with a list
    under some key. Adjust `_extract_records` once you've seen a real response.

    Beyond the top-level scalar columns pandas produces on its own, this adds
    one column per configured `fields.*` JSON path (resolved against the
    original nested record, not the normalized frame) plus a handful of
    `derived.*` columns for values that require picking apart a list (the
    defining event, the finding order, the pilot hours matrix, the FAR part).
    """
    # Only cases_*.json (rows from the FileExport CSV). The page_NN.json files
    # saved next to them are the verbatim Query/Main summary pages, a different shape.
    files = sorted(glob.glob(str(RAW / "**" / "cases_*.json"), recursive=True))
    if not files:
        raise SystemExit("No raw cases_*.json under data/raw/. Run fetch.py first.")
    records: list[dict] = []
    for fp in files:
        with open(fp) as f:
            payload = json.load(f)
        records.extend(_extract_records(payload))

    multi_aircraft = sum(1 for r in records if isinstance(r.get("aircrafts"), list) and len(r["aircrafts"]) > 1)
    print(
        f"load_raw_frame: {multi_aircraft}/{len(records)} records have more than one aircraft "
        "— taking aircrafts[0] by convention",
        file=sys.stderr,
    )

    df = pd.json_normalize(records)

    cfg = load_config()
    for name in _configured_field_names(cfg):
        if name in DERIVED_COLUMNS or name in df.columns:
            continue
        df[name] = [resolve_path(r, name) for r in records]

    df["derived.eventCodes"] = [_event_codes(r) or [] for r in records]
    df["derived.findingCodes"] = [_finding_codes(r) or [] for r in records]
    df["derived.pilotTotalHours"] = [_pilot_flight_hours(r, "All AC") for r in records]
    df["derived.pilotHoursInMakeModel"] = [_pilot_flight_hours(r, "Make and Model") for r in records]
    df["derived.far"] = [_far(r) for r in records]
    df["derived.phaseOfFlight"] = [_phase_of_flight(r) for r in records]

    df.attrs["source_files"] = files
    return df


def _extract_records(payload: Any) -> list[dict]:
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
        # observed: aircrafts[0].ownerOperators[0].regulationFlightConductedUnder == "091"
        df = df[df["derived.far"] == "091"]
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
