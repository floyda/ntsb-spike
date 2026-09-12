"""Session 6 — cross-tab Andy's decidability labels against narrative presence
and model abstention. Run after decidability.py.

Usage:
    python scripts/decidability_crosscheck.py
"""
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]

df = pd.read_csv(ROOT / "labelling" / "decidability.filled.csv", dtype=str).fillna("")
cfg = yaml.safe_load(open(ROOT / "config.yaml"))
full = pd.read_parquet(ROOT / "data/processed/filtered.parquet")
idc = cfg["fields"]["id"]
narr_col = cfg["fields"]["evidence"]["factual_narrative"]

sub = full[full[idc].isin(df["case_id"])].set_index(idc)
df["has_narrative"] = df["case_id"].map(
    sub[narr_col].map(lambda v: bool(str(v).strip()) and str(v) != "None" and not pd.isna(v))
)
df["correct"] = pd.to_numeric(df["occurrence_correct"], errors="coerce").fillna(0).astype(int)
df["abstained"] = df["model_abstained"] == "True"

print("occurrence_correct by narrative presence:")
print(pd.crosstab(df["has_narrative"], df["correct"], margins=True).to_string())
for flag, label in [(True, "WITH narrative"), (False, "WITHOUT narrative")]:
    d = df[df["has_narrative"] == flag]
    if len(d):
        print(f"  accuracy {label}: {d['correct'].mean():.0%}  (n={len(d)})")

print("\ncategory by narrative presence (misses only):")
misses = df[df["correct"] == 0].copy()
misses["category"] = misses["category"].str.upper().str.strip().replace("", "(blank)")
print(pd.crosstab(misses["has_narrative"], misses["category"]).to_string())

print("\nabstained vs judged-correct sanity:")
print(pd.crosstab(df["abstained"], df["correct"]).to_string())
