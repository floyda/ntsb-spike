"""Profile what a V2 API case record contains as a function of its age when fetched.

Question: when a case FIRST appears (days-to-weeks after the accident, investigation
still open), what evidence and what answer fields are already populated? Informs
whether a probable-cause agent could run on live cases.

Loads every data/raw/**/cases_*.json (the verbatim data[] concatenations written by
ntsb_spike.fetch). Each file lives under a fetched=YYYY-MM-DD directory; that date is
the observation date, so age = fetch_date - eventDate. Cases seen in more than one
fetch are deduplicated by mKey keeping the most recent fetch.

Usage:
    .venv/bin/python scripts/fresh_case_profile.py
"""
from __future__ import annotations

import json
import re
import statistics
import sys
from datetime import date
from pathlib import Path

RAW = Path(__file__).resolve().parent.parent / "data" / "raw"

BUCKETS = [
    ("0-14d", 0, 14),
    ("15-60d", 15, 60),
    ("61-180d", 61, 180),
    ("181-365d", 181, 365),
    (">365d", 366, 10**9),
]

FIELDS = [
    "prelimNarrative",
    "concatFactualNarr",
    "analysisNarrative",
    "probableCause",
    "findings[]",
    "events[]",
    "wx[0].metar",
    "pilotFlightTimeMatrix",
    "aircraftMake",
    "highestInjuryLevel",
]


def _nonempty(x) -> bool:
    if x is None:
        return False
    if isinstance(x, str):
        return bool(x.strip())
    if isinstance(x, (list, dict)):
        return len(x) > 0
    return True


def _narr(case: dict, key: str) -> str:
    """Longest non-empty value of `key` across the case's narratives[] entries."""
    vals = [n.get(key) or "" for n in (case.get("narratives") or [])]
    vals = [v for v in vals if v.strip()]
    return max(vals, key=len) if vals else ""


def profile(case: dict) -> dict[str, bool]:
    aircrafts = case.get("aircrafts") or []
    ac0 = aircrafts[0] if aircrafts else {}
    wx = case.get("weatherConditions") or []
    crew0 = (ac0.get("crewAndOccupants") or [{}])
    crew0 = crew0[0] if crew0 else {}
    return {
        "prelimNarrative": _nonempty(_narr(case, "prelimNarrative")),
        "concatFactualNarr": _nonempty(_narr(case, "concatenatedFactualNarrative")),
        "analysisNarrative": _nonempty(_narr(case, "analysisNarrative")),
        "probableCause": _nonempty(_narr(case, "probableCause")),
        "findings[]": any(_nonempty(a.get("findings")) for a in aircrafts),
        "events[]": any(_nonempty(a.get("events")) for a in aircrafts),
        "wx[0].metar": _nonempty(wx[0].get("metar")) if wx else False,
        "pilotFlightTimeMatrix": _nonempty(crew0.get("pilotsFlightTimeMatrix")),
        "aircraftMake": _nonempty(ac0.get("aircraftMake")),
        "highestInjuryLevel": _nonempty(case.get("highestInjuryLevel")),
    }


def load_cases() -> list[tuple[dict, date]]:
    """All raw cases with their fetch date, deduplicated by mKey (latest fetch wins)."""
    by_key: dict = {}
    files = sorted(RAW.glob("**/cases_*.json"))
    if not files:
        sys.exit(f"no cases_*.json under {RAW}")
    for f in files:
        m = re.search(r"fetched=(\d{4}-\d{2}-\d{2})", str(f.parent))
        fetched = date.fromisoformat(m.group(1)) if m else date.today()
        for case in json.load(open(f)):
            k = case.get("mKey") or case.get("ntsbNumber")
            prev = by_key.get(k)
            if prev is None or fetched >= prev[1]:
                by_key[k] = (case, fetched)
    print(f"loaded {len(files)} files, {len(by_key)} unique cases", file=sys.stderr)
    return list(by_key.values())


def bucket_of(age_days: int) -> str:
    for name, lo, hi in BUCKETS:
        if lo <= age_days <= hi:
            return name
    return "?"


def summarise(rows: list[dict], prelim_lens: list[int]) -> list[str]:
    n = len(rows)
    if n == 0:
        return ["0"] + ["-"] * (len(FIELDS) + 1)
    cells = [str(n)]
    for f in FIELDS:
        cells.append(f"{100.0 * sum(r[f] for r in rows) / n:.0f}%")
    cells.append(str(int(statistics.median(prelim_lens))) if prelim_lens else "-")
    return cells


def main() -> None:
    cases = load_cases()

    groups: dict[str, list[dict]] = {name: [] for name, _, _ in BUCKETS}
    lens: dict[str, list[int]] = {name: [] for name, _, _ in BUCKETS}
    closed_rows: list[dict] = []
    closed_lens: list[int] = []
    youngest: list[tuple[int, dict]] = []  # (age, case) in the 0-14d open bucket

    for case, fetched in cases:
        ev = case.get("eventDate") or ""
        try:
            age = (fetched - date.fromisoformat(ev[:10])).days
        except ValueError:
            continue
        p = profile(case)
        plen = len(_narr(case, "prelimNarrative"))
        if case.get("completionStatus") == "Completed":
            closed_rows.append(p)
            if plen:
                closed_lens.append(plen)
        else:
            b = bucket_of(max(age, 0))
            groups[b].append(p)
            if plen:
                lens[b].append(plen)
            if b == "0-14d":
                youngest.append((age, case))

    header = ["bucket", "n"] + FIELDS + ["med_prelim_len"]
    widths = [max(9, len(h) + 1) for h in header]

    def row(cells: list[str]) -> str:
        return "".join(c.ljust(w) for c, w in zip(cells, widths))

    print("\nOPEN cases (completionStatus != 'Completed'), bucketed by fetch_date - eventDate")
    print(row(header))
    print(row(["-" * (w - 1) for w in widths]))
    for name, _, _ in BUCKETS:
        print(row([name] + summarise(groups[name], lens[name])))
    print(row(["CLOSED"] + summarise(closed_rows, closed_lens)) + "   (all ages, comparison)")

    # Youngest bucket: prelim presence by age in days, and one example record's shape.
    if youngest:
        print("\n0-14d open cases — prelim presence by exact age (age_days: with/total):")
        by_age: dict[int, list[bool]] = {}
        for age, case in youngest:
            by_age.setdefault(age, []).append(bool(_narr(case, "prelimNarrative")))
        for age in sorted(by_age):
            v = by_age[age]
            print(f"  {age:>3}d: {sum(v)}/{len(v)}")

        age, ex = sorted(youngest, key=lambda t: t[0])[0]
        print(f"\nExample youngest open case: ntsbNumber={ex.get('ntsbNumber')} "
              f"mKey={ex.get('mKey')} eventDate={ex.get('eventDate')} age={age}d")
        pop = sorted(k for k, v in ex.items() if _nonempty(v))
        print(f"  populated top-level fields ({len(pop)}): {', '.join(pop)}")
        for label, obj in [
            ("narratives[0]", (ex.get("narratives") or [None])[0]),
            ("aircrafts[0]", (ex.get("aircrafts") or [None])[0]),
            ("weatherConditions[0]", (ex.get("weatherConditions") or [None])[0]),
        ]:
            if isinstance(obj, dict):
                sub = sorted(k for k, v in obj.items() if _nonempty(v))
                print(f"  {label} populated keys ({len(sub)}): {', '.join(sub)}")
            else:
                print(f"  {label}: ABSENT")
        ac = (ex.get("aircrafts") or [{}])[0]
        crew = ac.get("crewAndOccupants") or []
        if crew and isinstance(crew[0], dict):
            sub = sorted(k for k, v in crew[0].items() if _nonempty(v))
            print(f"  aircrafts[0].crewAndOccupants[0] populated keys ({len(sub)}): {', '.join(sub)}")
        else:
            print("  aircrafts[0].crewAndOccupants: EMPTY")


if __name__ == "__main__":
    main()
