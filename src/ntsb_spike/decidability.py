"""Session 6 — compute the agency number from your filled-in sheet.

Usage:
    python -m ntsb_spike.decidability
"""
from __future__ import annotations

import pandas as pd

from .common import ROOT

LABELLING = ROOT / "labelling"


def main() -> None:
    fp = LABELLING / "decidability.filled.csv"
    if not fp.exists():
        raise SystemExit("Fill in labelling/decidability.csv and save as decidability.filled.csv first.")
    df = pd.read_csv(fp, dtype=str)
    n = len(df)
    correct = pd.to_numeric(df["occurrence_correct"], errors="coerce").fillna(0)
    top3 = pd.to_numeric(df["top3_correct"], errors="coerce").fillna(0)
    print(f"One-shot, n={n}: occurrence top-1 {100 * correct.mean():.0f}%   top-3 {100 * top3.mean():.0f}%")
    print("Compare to baseline.py — the one-shot must beat the conditional modal baseline.\n")

    misses = df[correct == 0]
    cats = misses["category"].str.upper().str.strip().value_counts()
    print("Misses by category:")
    for c in "ABCD":
        print(f"  {c}: {cats.get(c, 0)}")
    wrong_rate = len(misses) / n
    bc_share = (cats.get("B", 0) + cats.get("C", 0)) / max(1, len(misses))
    agency = wrong_rate * bc_share
    print(f"\nwrong-rate {100 * wrong_rate:.0f}%  ×  B+C share {100 * bc_share:.0f}%  =  {100 * agency:.0f}%")
    verdict = ("✅ agent justified (≥20%)" if agency >= 0.20 else
               "⚠️ grey zone (15–20%) — inspect which cases are C" if agency >= 0.15 else
               "❌ classifier in disguise (<15%)")
    print(f"A6: {verdict}")

    tools = misses.loc[misses["category"].str.upper().str.strip() == "C", "tool_that_would_fix_it"]
    tools = tools.fillna("").str.lower().str.split("[,/|]").explode().str.strip()
    tools = tools[tools != ""]
    if len(tools):
        print("\nTool priority (from C cases):")
        print(tools.value_counts().to_string())


if __name__ == "__main__":
    main()
