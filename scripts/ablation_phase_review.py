"""Adjust the phase_of_flight ablation score for judge false negatives.

`scripts/ablation_phase.py` scored the ablated run with a Haiku equivalence
judge whose calibration against Andy's labels was poor and one-sided (it called
14 of Andy's 23 correct answers wrong). The orchestrating agent read every case
that flipped right->wrong under the judge and recorded, per case, whether the
ablated top-1 names the same occurrence as the original answer Andy marked
correct. Those verdicts live in
labelling/ablation.no_phase_of_flight.review.model.csv — a MODEL's opinion,
not ground truth. This script applies them and prints the adjusted number.

Usage:
    .venv/bin/python scripts/ablation_phase_review.py
"""
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
LAB = ROOT / "labelling"

df = pd.read_csv(LAB / "ablation.no_phase_of_flight.model.csv", comment="#", dtype=str).fillna("")
rev = pd.read_csv(LAB / "ablation.no_phase_of_flight.review.model.csv", dtype=str).fillna("")

truthy = {"1", "1.0", "True", "true"}
df["orig1"] = df["orig_top1_correct"].isin(truthy)
df["abl1"] = df["abl_top1_correct"].isin(truthy)
df["narr"] = df["has_narrative"].isin(truthy)

flips = df[df["orig1"] & ~df["abl1"]]
assert set(flips["case_id"]) == set(rev["case_id"]), "review file must cover exactly the right->wrong flips"

override = dict(zip(rev["case_id"], rev["reviewer_verdict"].isin(truthy)))
df["abl1_adj"] = [override.get(c, v) for c, v in zip(df["case_id"], df["abl1"])]

n = len(df)
print(f"n = {n}")
print(f"original top-1 (Andy):                 {100 * df['orig1'].mean():.1f}%")
print(f"ablated  top-1 (judge, lower bound):    {100 * df['abl1'].mean():.1f}%")
print(f"ablated  top-1 (judge + reviewer read): {100 * df['abl1_adj'].mean():.1f}%")
print(f"right->wrong flips under judge: {len(flips)}; upheld by reviewer: {int((~rev['reviewer_verdict'].isin(truthy)).sum())}")
for flag, label in [(True, "WITH narrative"), (False, "WITHOUT narrative")]:
    d = df[df["narr"] == flag]
    print(f"  {label:18s} n={len(d):2d}  orig {100 * d['orig1'].mean():.1f}%  "
          f"abl(judge) {100 * d['abl1'].mean():.1f}%  abl(adj) {100 * d['abl1_adj'].mean():.1f}%")
print("\nCaveat: 'adj' replaces judge verdicts with the orchestrating agent's read on the")
print("9 flipped cases only; wrong->wrong cases were not re-read. Model opinion, not ground truth.")
