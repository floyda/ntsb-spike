"""Session 6 — one-shot ceiling: single-message model run, no tools.

Writes labelling/decidability.csv with the model's answer next to the NTSB's,
plus an empty `category` column for you to fill (A/B/C/D) on the misses.

Usage:
    python -m ntsb_spike.oneshot          # runs on 40 stratified held-out cases
    python -m ntsb_spike.oneshot --dry    # builds the prompts and asserts no leakage, calls nothing

Requires: claude CLI logged in to a subscription. Command issued internally:
    claude -p --model {name} --effort {effort} --tools "" --system-prompt SYSTEM --output-format json --json-schema <schema>
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

import numpy as np
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
        if col and col in row.index:
            val = row[col]
            # Handle arrays (numpy/pandas) by checking if they contain data
            # For scalars, use standard pd.notna check
            try:
                is_notnull = pd.notna(val) if not isinstance(val, np.ndarray) else val.size > 0
            except (ValueError, TypeError):
                is_notnull = val is not None
            if is_notnull:
                # Convert numpy arrays to lists for JSON serialization
                if isinstance(val, np.ndarray):
                    val = val.tolist()
                ev[role] = val if not isinstance(val, (list, dict)) else json.dumps(val)
    return ev


def assert_no_answer_fields(cfg: dict, evidence: dict) -> None:
    """Leakage guard: no answer field name or value may appear in the evidence payload."""
    ans = cfg["fields"]["answer"]
    for role in ans:
        assert role not in evidence, f"answer role {role} present in evidence"
    return None


def call_model(cfg: dict, evidence: dict) -> tuple[OneShotAnswer, float | None]:
    """Call the Claude model via the claude CLI in headless mode.

    Args:
        cfg: Configuration dict with model settings.
        evidence: Evidence payload (no answer fields).

    Returns:
        Tuple of (validated OneShotAnswer, total_cost_usd or None).

    Raises:
        RuntimeError: If CLI exits nonzero or times out.
    """
    schema = json.dumps(OneShotAnswer.model_json_schema())
    model_name = cfg["model"]["name"]
    effort = cfg["model"].get("effort", "medium")

    # Build claude CLI command
    cmd = [
        "claude",
        "-p",
        "--model",
        model_name,
        "--effort",
        effort,
        "--tools",
        "",
        "--system-prompt",
        SYSTEM,
        "--output-format",
        "json",
        "--json-schema",
        schema,
    ]

    # Prepare subprocess environment: remove API key to force subscription auth
    env = os.environ.copy()
    env.pop("ANTHROPIC_API_KEY", None)
    env.pop("CLAUDECODE", None)
    env.pop("CLAUDE_CODE_ENTRYPOINT", None)

    # Run CLI with evidence as stdin
    try:
        result = subprocess.run(
            cmd,
            input=json.dumps(evidence, indent=1),
            capture_output=True,
            text=True,
            timeout=300,
            env=env,
        )
    except subprocess.TimeoutExpired as e:
        raise RuntimeError(f"claude CLI timeout (300s): {e.stderr}") from e

    if result.returncode != 0:
        raise RuntimeError(
            f"claude CLI exited with code {result.returncode}: {result.stderr}"
        )

    # Parse JSON response (CLI returns an array of events; extract the result)
    try:
        output = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"failed to parse JSON response: {e}") from e

    # CLI returns an array; find the result object (type=result, subtype=success)
    response = None
    if isinstance(output, list):
        for item in output:
            if item.get("type") == "result" and item.get("subtype") == "success":
                response = item
                break
    elif isinstance(output, dict):
        # Fallback: might be a single dict response
        response = output

    if not response:
        raise RuntimeError(
            f"no successful result in CLI output: {json.dumps(output)[:200]}"
        )

    # Extract cost
    cost: float | None = response.get("total_cost_usd")

    # Extract and validate answer
    if "structured_output" in response and response["structured_output"]:
        ans = OneShotAnswer.model_validate(response["structured_output"])
    else:
        # Fallback: parse result field as JSON
        text = response.get("result", "").strip().strip("`")
        if text.startswith("json"):
            text = text[4:]
        ans = OneShotAnswer.model_validate_json(text)

    return ans, cost


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
    total_cost: float = 0.0
    for _, row in sample.iterrows():
        evidence = build_evidence(cfg, row)
        assert_no_answer_fields(cfg, evidence)
        ans = None
        cost = None
        if dry:
            ans = None
            cost = None
        else:
            try:
                ans, cost = call_model(cfg, evidence)
                if cost is not None:
                    total_cost += cost
            except (ValidationError, RuntimeError, json.JSONDecodeError) as e:
                print(f"model failure on {row[idc]}: {e}", file=sys.stderr)
                ans = None
                cost = None
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
            "model_cost_usd": cost if cost is not None else "",
        })
    LABELLING.mkdir(exist_ok=True)
    out = LABELLING / "decidability.csv"
    pd.DataFrame(rows).to_csv(out, index=False)
    if not dry:
        print(f"total reported cost: ${total_cost:.4f} (would-be API price; subscription marginal cost is nil)")
    print(f"{'DRY RUN — ' if dry else ''}wrote {out} with {len(rows)} cases. Fill in the last four columns, save as decidability.filled.csv.")


if __name__ == "__main__":
    main()
