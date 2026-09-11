"""Session 3 — modal baselines (unconditional and conditional).

This is the ONE script allowed to read answer fields freely, because a baseline
is a property of the answers. It never passes anything to a model.

Only condition on fields Session 4 kept in the evidence half — see config.yaml.

Usage:
    python -m ntsb_spike.baseline
"""
from __future__ import annotations

import pandas as pd

from .common import answer_field, load_config, stratified_sample
from .volume import explode_codes


def primary_code(v) -> str | None:
    if isinstance(v, list):
        return v[0] if v else None
    if isinstance(v, str):
        parts = [c.strip() for c in v.replace(";", ",").split(",") if c.strip()]
        return parts[0] if parts else None
    return None


def modal_baseline(df: pd.DataFrame, target: str, condition: str | None) -> dict:
    """Guess the most common target (per condition group if given). Score top-1 and top-3."""
    if condition is None:
        ranked = df[target].value_counts().index.tolist()
        top1 = (df[target] == ranked[0]).mean()
        top3 = df[target].isin(ranked[:3]).mean()
        return {"condition": "none", "top1": top1, "top3": top3}
    hits1 = hits3 = 0
    for _, grp in df.groupby(condition):
        ranked = grp[target].value_counts().index.tolist()
        hits1 += (grp[target] == ranked[0]).sum()
        hits3 += grp[target].isin(ranked[:3]).sum()
    return {"condition": condition, "top1": hits1 / len(df), "top3": hits3 / len(df)}


def finding_code_baseline(df: pd.DataFrame, occ_col: str, find_col: str) -> dict:
    """For each case, predict the finding codes most often seen with its (modal-predicted) occurrence."""
    modal_occ = df[occ_col].value_counts().index[0]
    codes = explode_codes(df[df[occ_col] == modal_occ][find_col]).value_counts()
    predicted = set(codes.head(3).index)
    p_sum = r_sum = 0.0
    for v in df[find_col]:
        actual = set(explode_codes(pd.Series([v])).tolist())
        if not predicted:
            continue
        tp = len(predicted & actual)
        p_sum += tp / len(predicted)
        r_sum += tp / len(actual) if actual else 0
    n = len(df)
    return {"predicted_set": sorted(predicted), "precision": p_sum / n, "recall": r_sum / n}


def main() -> None:
    cfg = load_config()
    df = pd.read_parquet("data/processed/filtered.parquet")
    df = df[df["_event_year"].isin(cfg["splits"]["test_years"])]
    occ = answer_field(cfg, "occurrence_codes")
    df = df.assign(_occ=df[occ].map(primary_code)).dropna(subset=["_occ"])
    sample = stratified_sample(df, "_occ", n=1000)

    print(f"Sample: {len(sample)} held-out cases\n")
    results = [modal_baseline(sample, "_occ", None)]
    ev = cfg["fields"]["evidence"]
    for cond_role in ("phase_of_flight", "weather_condition"):
        col = ev.get(cond_role)
        if col:
            results.append(modal_baseline(sample, "_occ", col))
    if ev.get("phase_of_flight") and ev.get("weather_condition"):
        sample = sample.assign(_phase_wx=sample[ev["phase_of_flight"]].astype(str) + "|" + sample[ev["weather_condition"]].astype(str))
        results.append(modal_baseline(sample, "_occ", "_phase_wx"))
    table = pd.DataFrame(results)
    table[["top1", "top3"]] = (table[["top1", "top3"]] * 100).round(1)
    print("Occurrence-code modal baselines (% correct):")
    print(table.to_string(index=False))

    top3_share = sample["_occ"].value_counts(normalize=True).head(3).sum()
    print(f"\nClass imbalance: top 3 occurrence codes = {100 * top3_share:.1f}% of cases")

    find = cfg["fields"]["answer"].get("finding_codes")
    if find:
        fb = finding_code_baseline(sample, "_occ", find)
        print(f"\nFinding-code baseline (predict {fb['predicted_set']} for everyone):")
        print(f"  precision {100 * fb['precision']:.1f}%   recall {100 * fb['recall']:.1f}%")

    best = table["top1"].max()
    print(f"\nA5: best conditional top-1 = {best:.1f}%  {'⚠️ above 50% — lift must be large' if best > 50 else '✅ room for lift'}")


if __name__ == "__main__":
    main()
