"""Session 6 — quick descriptive stats over labelling/decidability.csv.

Reports run health only (abstentions, confidence, cost). Correctness is Andy's
call via the occurrence_correct / category columns — no accuracy is computed here.

Usage:
    python scripts/oneshot_summary.py
"""
from pathlib import Path

import pandas as pd

df = pd.read_csv(Path(__file__).resolve().parents[1] / "labelling" / "decidability.csv")

n = len(df)
answered = df["model_occurrence"].astype(str).str.len().gt(0).sum()
abstained = df["model_abstained"].fillna(False).astype(bool).sum()
conf = pd.to_numeric(df["model_confidence"], errors="coerce")
cost = pd.to_numeric(df["model_cost_usd"], errors="coerce")

print(f"cases: {n}  answered: {answered}  abstained: {abstained}")
print(f"confidence: mean {conf.mean():.2f}  min {conf.min():.2f}  max {conf.max():.2f}")
print(f"cost/case USD: mean {cost.mean():.4f}  median {cost.median():.4f}  "
      f"max {cost.max():.4f}  total {cost.sum():.4f}")
gbp = 0.74
print(f"cost/case GBP (at {gbp} USD/GBP... i.e. *{gbp}): mean £{cost.mean() * gbp:.4f}  "
      f"A7 line £0.05 -> {'under' if cost.mean() * gbp < 0.05 else 'OVER'}")

# Abstention vs missing factual narrative — do they coincide?
import yaml
from ntsb_spike.oneshot import build_evidence

cfg = yaml.safe_load(open(Path(__file__).resolve().parents[1] / "config.yaml"))
full = pd.read_parquet(Path(__file__).resolve().parents[1] / "data/processed/filtered.parquet")
idc = cfg["fields"]["id"]
sub = full[full[idc].isin(df["case_id"])]
has_narr = {
    r[idc]: "factual_narrative" in build_evidence(cfg, r) and bool(str(r[cfg["fields"]["evidence"]["factual_narrative"]]).strip())
    for _, r in sub.iterrows()
}
df["_has_narrative"] = df["case_id"].map(has_narr)
ct = pd.crosstab(df["_has_narrative"], df["model_abstained"].fillna(False).astype(bool))
print("\nabstained (cols) vs has factual narrative (rows):")
print(ct.to_string())
