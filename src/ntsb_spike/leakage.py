"""Session 4 — leakage check.

Two parts:
  1. `sheet`  — write labelling/leakage.csv with 30 stratified factual accounts and the
                answer columns hidden, for blind reading. Answers go to a separate key file.
  2. `scan`   — count give-away phrases in ALL factual accounts, and report which
                structured evidence fields correlate suspiciously with the answer.
  3. `score`  — after you fill labelling/leakage.filled.csv, compare your guesses to the key.

Usage:
    python -m ntsb_spike.leakage sheet
    python -m ntsb_spike.leakage scan
    python -m ntsb_spike.leakage score
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pandas as pd

from .common import ROOT, answer_field, evidence_field, load_config, stratified_sample
from .baseline import primary_code

LABELLING = ROOT / "labelling"

# Words that state a judgement rather than a fact. Extend after reading real accounts.
GIVEAWAY = [
    r"\bfailed to\b", r"\bfailure to\b", r"\binadequate\b", r"\bimproper(ly)?\b",
    r"\bdid not maintain\b", r"\bdelayed\b", r"\bmisjudg", r"\bexceeded\b",
    r"\bpilot's decision\b", r"\bcontributing\b", r"\bprobable\b", r"\bresulted in\b",
]


def load_test(cfg):
    df = pd.read_parquet("data/processed/filtered.parquet")
    df = df[df["_event_year"].isin(cfg["splits"]["test_years"])]
    occ = answer_field(cfg, "occurrence_codes")
    return df.assign(_occ=df[occ].map(primary_code)).dropna(subset=["_occ"])


def cmd_sheet(cfg):
    df = load_test(cfg)
    s = stratified_sample(df, "_occ", n=30)
    idc = cfg["fields"]["id"]
    fact = evidence_field(cfg, "factual_narrative")
    sheet = pd.DataFrame({
        "case_id": s[idc].astype(str),
        "factual_account": s[fact],
        "your_guess_at_cause": "",
        "your_confidence_0_to_1": "",
        "sentences_that_state_a_conclusion": "",
    })
    key = pd.DataFrame({
        "case_id": s[idc].astype(str),
        "occurrence_code": s["_occ"],
        "probable_cause": s[answer_field(cfg, "probable_cause")],
    })
    LABELLING.mkdir(exist_ok=True)
    sheet.to_csv(LABELLING / "leakage.csv", index=False)
    key.to_csv(LABELLING / "leakage.KEY.csv", index=False)
    print("Wrote labelling/leakage.csv (read this) and labelling/leakage.KEY.csv (do NOT open until done).")
    print("Save your answers as labelling/leakage.filled.csv, then run `score`.")


def cmd_scan(cfg):
    df = load_test(cfg)
    fact = evidence_field(cfg, "factual_narrative")
    pat = re.compile("|".join(GIVEAWAY), re.IGNORECASE)
    hits = df[fact].fillna("").map(lambda t: bool(pat.search(t)))
    print(f"Accounts containing at least one give-away phrase: {100 * hits.mean():.1f}%  (n={len(df)})")
    counts = {p: int(df[fact].fillna("").str.contains(p, case=False, regex=True).sum()) for p in GIVEAWAY}
    print("\nPer phrase:")
    for p, c in sorted(counts.items(), key=lambda kv: -kv[1]):
        print(f"  {c:>6}  {p}")

    # Structured fields that predict the answer too well are answers in disguise.
    print("\nEvidence fields vs occurrence code — how many distinct occurrence codes per field value?")
    print("(A field where each value maps to one code is the verdict in disguise — move it to answer.)")
    for role, col in cfg["fields"]["evidence"].items():
        if not col or col == fact or df[col].nunique() > 200:
            continue
        per_value = df.groupby(col)["_occ"].nunique()
        purity = (per_value == 1).mean()
        print(f"  {role:<20} {col:<30} values: {df[col].nunique():>4}   share of values mapping to exactly one code: {100 * purity:.0f}%")


def cmd_score(cfg):
    filled = LABELLING / "leakage.filled.csv"
    if not filled.exists():
        raise SystemExit("Fill in labelling/leakage.csv and save it as labelling/leakage.filled.csv first.")
    mine = pd.read_csv(filled, dtype=str)
    key = pd.read_csv(LABELLING / "leakage.KEY.csv", dtype=str)
    m = mine.merge(key, on="case_id")
    print("Compare your guess to the probable cause by eye — mark a column `correct` (1/0) in the filled sheet.")
    if "correct" in m.columns:
        acc = pd.to_numeric(m["correct"], errors="coerce").mean()
        print(f"Your accuracy from the factual account alone: {100 * acc:.0f}%")
        print("A4 rule of thumb: if a non-expert is right most of the time, the evidence is leaking.")
    flagged = m["sentences_that_state_a_conclusion"].fillna("").str.strip().ne("").mean()
    print(f"Accounts where you flagged a conclusion-style sentence: {100 * flagged:.0f}%  (kill if > 20%)")


def main():
    cmds = {"sheet": cmd_sheet, "scan": cmd_scan, "score": cmd_score}
    if len(sys.argv) != 2 or sys.argv[1] not in cmds:
        raise SystemExit(__doc__)
    cmds[sys.argv[1]](load_config())


if __name__ == "__main__":
    main()
