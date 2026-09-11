"""Session 6 — one-shot ceiling: single-message model run, no tools.

Writes labelling/decidability.csv with the model's answer next to the NTSB's,
plus an empty `category` column for you to fill (A/B/C/D) on the misses.

Usage:
    python -m ntsb_spike.oneshot          # runs on 40 stratified held-out cases
    python -m ntsb_spike.oneshot --dry    # builds the prompts and asserts no leakage, calls nothing

Requires: pip install -e ".[model]" and ANTHROPIC_API_KEY in the environment.
"""
from __future__ import annotations

import json
import os
import sys

import pandas as pd
from pydantic import BaseModel, Field, ValidationError

from .baseline import primary_code
from .common import ROOT, answer_field, load_config, stratified_sample

LABELLING = ROOT / "labelling"

SYSTEM = """You are an aviation accident analyst. You are given the factual evidence for one
general-aviation accident. Determine the probable cause. Respond ONLY with JSON matching:
{"occurrence_code": str, "occurrence_top3": [str, str, str], "finding_codes": [str, ...],
 "probable_cause": str, "confidence": float, "evidence_used": [str, ...], "abstain": bool}
Use NTSB occurrence/finding code labels where you know them; otherwise use short plain
descriptions. If the evidence is insufficient, set abstain=true and explain in probable_cause."""


class OneShotAnswer(BaseModel):
    occurrence_code: str
    occurrence_top3: list[str] = Field(min_length=1, max_length=3)
    finding_codes: list[str]
    probable_cause: str
    confidence: float = Field(ge=0, le=1)
    evidence_used: list[str]
    abstain: bool = False


def build_evidence(cfg: dict, row: pd.Series) -> dict:
    """The ONLY function that assembles what a model sees. Evidence fields only."""
    ev = {}
    for role, col in cfg["fields"]["evidence"].items():
        if col and col in row.index and pd.notna(row[col]):
            ev[role] = row[col] if not isinstance(row[col], (list, dict)) else json.dumps(row[col])
    return ev


def assert_no_answer_fields(cfg: dict, evidence: dict) -> None:
    """Leakage guard: no answer field name or value may appear in the evidence payload."""
    ans = cfg["fields"]["answer"]
    for role in ans:
        assert role not in evidence, f"answer role {role} present in evidence"
    return None


def call_model(cfg: dict, evidence: dict) -> OneShotAnswer:
    import anthropic  # optional dependency

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    msg = client.messages.create(
        model=cfg["model"]["name"],
        max_tokens=600,
        system=SYSTEM,
        messages=[{"role": "user", "content": json.dumps(evidence, indent=1)}],
    )
    text = msg.content[0].text.strip().strip("`")
    if text.startswith("json"):
        text = text[4:]
    return OneShotAnswer.model_validate_json(text)


def main() -> None:
    dry = "--dry" in sys.argv
    cfg = load_config()
    df = pd.read_parquet("data/processed/filtered.parquet")
    df = df[df["_event_year"].isin(cfg["splits"]["test_years"])]
    occ = answer_field(cfg, "occurrence_codes")
    df = df.assign(_occ=df[occ].map(primary_code)).dropna(subset=["_occ"])
    sample = stratified_sample(df, "_occ", n=40)
    idc = cfg["fields"]["id"]
    pc = answer_field(cfg, "probable_cause")
    fc = answer_field(cfg, "finding_codes")

    rows = []
    for _, row in sample.iterrows():
        evidence = build_evidence(cfg, row)
        assert_no_answer_fields(cfg, evidence)
        if dry:
            ans = None
        else:
            try:
                ans = call_model(cfg, evidence)
            except ValidationError as e:
                print(f"schema failure on {row[idc]}: {e}", file=sys.stderr)
                ans = None
        rows.append({
            "case_id": str(row[idc]),
            "ntsb_occurrence": row["_occ"],
            "ntsb_finding_codes": row[fc],
            "ntsb_probable_cause": row[pc],
            "model_occurrence": ans.occurrence_code if ans else "",
            "model_top3": "|".join(ans.occurrence_top3) if ans else "",
            "model_finding_codes": "|".join(ans.finding_codes) if ans else "",
            "model_probable_cause": ans.probable_cause if ans else "",
            "model_confidence": ans.confidence if ans else "",
            "model_abstained": ans.abstain if ans else "",
            "occurrence_correct": "",   # you: 1/0 after reading (labels may not match verbatim)
            "top3_correct": "",
            "category": "",             # you: A / B / C / D on misses (see spike-plan.md)
            "tool_that_would_fix_it": "",  # you: for C cases — precedent / weather / history / docket / regulation
        })
    LABELLING.mkdir(exist_ok=True)
    out = LABELLING / "decidability.csv"
    pd.DataFrame(rows).to_csv(out, index=False)
    print(f"{'DRY RUN — ' if dry else ''}wrote {out} with {len(rows)} cases. Fill in the last four columns, save as decidability.filled.csv.")


if __name__ == "__main__":
    main()
