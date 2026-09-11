"""Session 2 — counts per year, time-to-close, code distributions, proposed splits.

Usage:
    python -m ntsb_spike.volume
"""
from __future__ import annotations

import pandas as pd

from .common import answer_field, load_config


def explode_codes(series: pd.Series) -> pd.Series:
    """Codes may be a list, a delimited string, or a scalar. Normalise to one code per row."""
    def to_list(v):
        # Parquet round-trips list columns as numpy arrays — accept any non-string sequence.
        if not isinstance(v, str) and hasattr(v, "__len__"):
            return list(v)
        if isinstance(v, str):
            return [c.strip() for c in v.replace(";", ",").split(",") if c.strip()]
        return []
    return series.map(to_list).explode().dropna()


def main() -> None:
    cfg = load_config()
    df = pd.read_parquet("data/processed/filtered.parquet")
    f = cfg["fields"]

    print("Cases per event year:")
    print(df["_event_year"].value_counts().sort_index().to_string())

    if f.get("probable_cause_date"):
        ev = pd.to_datetime(df[f["event_date"]], errors="coerce")
        pcd = pd.to_datetime(df[f["probable_cause_date"]], errors="coerce")
        days = (pcd - ev).dt.days.dropna()
        recent = days[ev[days.index].dt.year >= ev.dt.year.max() - 2]
        print("\nTime to close (days), cases from the last two years:")
        print(recent.describe(percentiles=[0.25, 0.5, 0.75]).round(0).to_string())
        print("\nA11: this is the number to design the live board around.")

    occ = answer_field(cfg, "occurrence_codes")
    print("\nOccurrence code distribution (top 15):")
    print(explode_codes(df[occ]).value_counts().head(15).to_string())

    phase = f["evidence"].get("phase_of_flight")
    if phase:
        print("\nPhase of flight distribution:")
        print(df[phase].value_counts().to_string())

    s = cfg["splits"]
    dev = (df["_event_year"] <= s["dev_max_year"]).sum()
    test = df["_event_year"].isin(s["test_years"]).sum()
    open_ = (df["_event_year"] >= s["open_min_year"]).sum()
    print(f"\nProposed splits — dev: {dev}  held-out: {test}  open: {open_}")
    print("Held-out should be ≥ 3,000 once you have fetched enough years.")


if __name__ == "__main__":
    main()
