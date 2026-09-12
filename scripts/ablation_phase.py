"""Score the phase_of_flight ablation of the 40-case one-shot — WITHOUT any new
human labelling.

Context: `ntsb_spike.oneshot --ablate phase_of_flight --out ablation.no_phase_of_flight.csv`
reruns the same 40 stratified held-out cases (same seed=7 draw as
labelling/decidability.csv) with `derived.phaseOfFlight` removed from the
evidence payload. Andy already hand-scored the ORIGINAL run in
labelling/decidability.filled.csv (occurrence_correct, top3_correct, category).
This script never touches those two files' judgement columns; it only reads them.

Transfer rule: where the ablated model's answer string is unchanged from the
original (normalised), Andy's original judgement is reused verbatim — he already
looked at that exact answer. Where the answer changed, an LLM "equivalence
judge" (Haiku, via the claude CLI) decides whether the new answer is still
correct against the NTSB's occurrence code/probable cause. The judge is a
SCORER, not a predictor: its prompt contains only the two answers being
compared (decoded NTSB occurrence label + NTSB probable-cause sentence, and the
model's occurrence/top-3/probable-cause) — no case evidence at all. Its output
is a model's opinion, clearly marked as such in the output CSV; it is not
ground truth and must not be treated as if Andy produced it.

The judge is calibrated by also running it over all 40 rows of the ORIGINAL
run's answers and comparing to Andy's occurrence_correct / top3_correct.

Usage:
    .venv/bin/python scripts/ablation_phase.py
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pandas as pd
import yaml
from pydantic import BaseModel, Field, ValidationError

ROOT = Path(__file__).resolve().parents[1]
LABELLING = ROOT / "labelling"

sys.path.insert(0, str(ROOT / "src"))
from ntsb_spike.baseline import primary_code  # noqa: E402
from ntsb_spike.decidability_form import build_code_lookups  # noqa: E402

JUDGE_MODEL = "claude-haiku-4-5-20251001"

# This is a SCORER prompt, not a predictor prompt: it never sees any case
# evidence (narrative, aircraft, pilot hours, weather, phase...). It only
# compares two already-produced answers (NTSB's vs. the model's) for
# semantic equivalence. It must not be confused with oneshot.build_evidence(),
# which remains the only place a model payload assembled from evidence is built.
JUDGE_SYSTEM = """You are scoring whether a candidate answer about an aviation accident's cause
matches the NTSB's official verdict. You are NOT investigating the accident and have NOT been
given any evidence about it — only the two verdicts to compare. Judge on substance, not exact
wording: a paraphrase that names the same underlying occurrence/cause is correct.

You will be given:
- the NTSB's official occurrence category (decoded label)
- the NTSB's official probable-cause sentence
- a candidate's stated top occurrence, its top-3 occurrence guesses, and its one-sentence
  probable cause

Decide:
- top1_correct: does the candidate's TOP occurrence match the NTSB's occurrence category
  (same underlying event type, not necessarily identical wording)?
- top3_correct: does ANY of the candidate's top-3 occurrence guesses match the NTSB's
  occurrence category?

Respond ONLY with JSON matching: {"top1_correct": bool, "top3_correct": bool, "reason": str}
Keep "reason" to one short sentence."""


class JudgeAnswer(BaseModel):
    top1_correct: bool
    top3_correct: bool
    reason: str = Field(default="")


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", str(s).strip().lower())


def _norm_set(pipe_str: str) -> frozenset[str]:
    return frozenset(_norm(x) for x in str(pipe_str).split("|") if _norm(x))


def call_judge(ntsb_label: str, ntsb_cause: str, model_occ: str, model_top3: str, model_cause: str) -> tuple[JudgeAnswer, float | None]:
    """Call the equivalence judge via the claude CLI (Haiku, subscription auth).

    Mirrors ntsb_spike.oneshot.call_model's CLI invocation and env-popping, but
    with a different model and a comparison-only prompt (no evidence fields).
    """
    schema = json.dumps(JudgeAnswer.model_json_schema())
    payload = {
        "ntsb_occurrence_label": ntsb_label,
        "ntsb_probable_cause": ntsb_cause,
        "candidate_top_occurrence": model_occ,
        "candidate_top3_occurrences": [x.strip() for x in str(model_top3).split("|") if x.strip()],
        "candidate_probable_cause": model_cause,
    }
    cmd = [
        "claude", "-p",
        "--model", JUDGE_MODEL,
        "--tools", "",
        "--system-prompt", JUDGE_SYSTEM,
        "--output-format", "json",
        "--json-schema", schema,
    ]
    env = os.environ.copy()
    env.pop("ANTHROPIC_API_KEY", None)
    env.pop("CLAUDECODE", None)
    env.pop("CLAUDE_CODE_ENTRYPOINT", None)

    result = subprocess.run(
        cmd, input=json.dumps(payload, indent=1), capture_output=True, text=True, timeout=120, env=env,
    )
    if result.returncode != 0:
        raise RuntimeError(f"judge CLI exited {result.returncode}: {result.stderr}")
    output = json.loads(result.stdout)
    response = None
    if isinstance(output, list):
        for item in output:
            if item.get("type") == "result" and item.get("subtype") == "success":
                response = item
                break
    elif isinstance(output, dict):
        response = output
    if not response:
        raise RuntimeError(f"no successful judge result: {json.dumps(output)[:200]}")
    cost = response.get("total_cost_usd")
    if "structured_output" in response and response["structured_output"]:
        ans = JudgeAnswer.model_validate(response["structured_output"])
    else:
        text = response.get("result", "").strip().strip("`")
        if text.startswith("json"):
            text = text[4:]
        ans = JudgeAnswer.model_validate_json(text)
    return ans, cost


def score_row(event_labels: dict, ntsb_occ_code: str, ntsb_cause: str, model_occ: str, model_top3: str, model_cause: str) -> tuple[JudgeAnswer, float | None]:
    label = event_labels.get(str(ntsb_occ_code), str(ntsb_occ_code))
    return call_judge(label, ntsb_cause, model_occ, model_top3, model_cause)


def has_narrative_map(cfg: dict, case_ids: list[str]) -> dict[str, bool]:
    full = pd.read_parquet(ROOT / "data/processed/filtered.parquet")
    idc = cfg["fields"]["id"]
    narr_col = cfg["fields"]["evidence"]["factual_narrative"]
    sub = full[full[idc].isin(case_ids)].set_index(idc)
    return sub[narr_col].map(lambda v: bool(str(v).strip()) and str(v) != "None" and not pd.isna(v)).to_dict()


def bool01(s) -> bool:
    return str(s).strip() in ("1", "1.0", "True", "true")


def confusion(a: pd.Series, b: pd.Series) -> str:
    """2x2 confusion of two 0/1-ish series (a=rows, b=cols)."""
    ct = pd.crosstab(a.map(bool01), b.map(bool01), rownames=["andy"], colnames=["judge"])
    return ct.to_string()


def main() -> None:
    cfg = yaml.safe_load(open(ROOT / "config.yaml"))
    orig = pd.read_csv(LABELLING / "decidability.filled.csv", dtype=str).fillna("")
    abl = pd.read_csv(LABELLING / "ablation.no_phase_of_flight.csv", dtype=str).fillna("")

    assert set(orig["case_id"]) == set(abl["case_id"]), "case_id sets differ between original and ablation runs"

    m = orig.merge(abl, on="case_id", suffixes=("_orig", "_abl"))
    assert len(m) == len(orig) == 40, f"expected 40 matched cases, got {len(m)}"

    event_labels, _finding_labels = build_code_lookups()
    narr = has_narrative_map(cfg, m["case_id"].tolist())

    out_rows = []
    judge_costs: list[float] = []
    n_judge_calls = 0
    n_judge_failures = 0

    for _, r in m.iterrows():
        case_id = r["case_id"]
        ntsb_occ = r["ntsb_occurrence_orig"]
        ntsb_cause = r["ntsb_probable_cause_orig"]
        ntsb_label = event_labels.get(str(ntsb_occ), str(ntsb_occ))
        orig_occ = r["model_occurrence_orig"]
        abl_occ = r["model_occurrence_abl"]
        orig_top3 = r["model_top3_orig"]
        abl_top3 = r["model_top3_abl"]
        orig_abstained = bool01(r["model_abstained_orig"])
        abl_abstained = str(r["model_abstained_abl"]).strip() in ("True", "true", "1")

        occ_unchanged = _norm(orig_occ) == _norm(abl_occ)
        top3_unchanged = _norm_set(orig_top3) == _norm_set(abl_top3)
        both_abstained = orig_abstained and abl_abstained

        orig_top1_correct = bool01(r["occurrence_correct_orig"])
        orig_top3_correct = bool01(r["top3_correct_orig"])

        abl_cost = pd.to_numeric(r.get("model_cost_usd_abl", ""), errors="coerce")

        judge_reason = ""

        if occ_unchanged or both_abstained:
            abl_top1_correct = orig_top1_correct
            abl_top1_source = "transferred"
        else:
            n_judge_calls += 1
            try:
                jr, jc = call_judge(ntsb_label, ntsb_cause, abl_occ, abl_top3, r["model_probable_cause_abl"])
                abl_top1_correct = jr.top1_correct
                judge_reason = jr.reason
                if jc:
                    judge_costs.append(jc)
            except (RuntimeError, ValidationError, json.JSONDecodeError) as e:
                n_judge_failures += 1
                print(f"judge failure (top1) on {case_id}: {e}", file=sys.stderr)
                abl_top1_correct = False
                judge_reason = f"[judge failed: {e}]"
            abl_top1_source = "judge"

        if top3_unchanged or both_abstained:
            abl_top3_correct = orig_top3_correct
            abl_top3_source = "transferred"
        else:
            if abl_top1_source == "judge" and judge_reason and not judge_reason.startswith("[judge failed"):
                # Reuse the same judge call's top3 verdict — one call gives both.
                abl_top3_correct = jr.top3_correct
                abl_top3_source = "judge"
            else:
                n_judge_calls += 1
                try:
                    jr2, jc2 = call_judge(ntsb_label, ntsb_cause, abl_occ, abl_top3, r["model_probable_cause_abl"])
                    abl_top3_correct = jr2.top3_correct
                    if not judge_reason:
                        judge_reason = jr2.reason
                    if jc2:
                        judge_costs.append(jc2)
                except (RuntimeError, ValidationError, json.JSONDecodeError) as e:
                    n_judge_failures += 1
                    print(f"judge failure (top3) on {case_id}: {e}", file=sys.stderr)
                    abl_top3_correct = False
                abl_top3_source = "judge"

        out_rows.append({
            "case_id": case_id,
            "has_narrative": bool(narr.get(case_id, False)),
            "ntsb_occurrence": ntsb_occ,
            "ntsb_label": ntsb_label,
            "orig_model_occurrence": orig_occ,
            "abl_model_occurrence": abl_occ,
            "answer_changed": not occ_unchanged,
            "orig_top1_correct": orig_top1_correct,
            "abl_top1_correct": bool(abl_top1_correct),
            "abl_top1_source": abl_top1_source,
            "orig_top3_correct": orig_top3_correct,
            "abl_top3_correct": bool(abl_top3_correct),
            "abl_top3_source": abl_top3_source,
            "orig_abstained": orig_abstained,
            "abl_abstained": abl_abstained,
            "judge_reason": judge_reason,
            "abl_cost_usd": abl_cost if pd.notna(abl_cost) else "",
        })

    out_df = pd.DataFrame(out_rows)
    LABELLING.mkdir(exist_ok=True)
    out_path = LABELLING / "ablation.no_phase_of_flight.model.csv"
    header_note = (
        "# MODEL'S OPINION, NOT GROUND TRUTH. abl_top1_correct/abl_top3_correct are transferred\n"
        "# from Andy's hand labels only where the answer string didn't change; where it changed,\n"
        "# they come from an LLM equivalence judge (Haiku) that saw no case evidence, only the two\n"
        "# verdicts being compared (abl_*_source == 'judge'). See scripts/ablation_phase.py.\n"
    )
    with open(out_path, "w") as f:
        f.write(header_note)
        out_df.to_csv(f, index=False)

    # ---- (d) judge calibration on the ORIGINAL run ----
    calib_rows = []
    calib_cost: list[float] = []
    for _, r in orig.iterrows():
        ntsb_label = event_labels.get(str(r["ntsb_occurrence"]), str(r["ntsb_occurrence"]))
        try:
            jr, jc = call_judge(ntsb_label, r["ntsb_probable_cause"], r["model_occurrence"], r["model_top3"], r["model_probable_cause"])
            if jc:
                calib_cost.append(jc)
            calib_rows.append({
                "case_id": r["case_id"],
                "andy_top1": bool01(r["occurrence_correct"]),
                "judge_top1": jr.top1_correct,
                "andy_top3": bool01(r["top3_correct"]),
                "judge_top3": jr.top3_correct,
            })
        except (RuntimeError, ValidationError, json.JSONDecodeError) as e:
            print(f"calibration judge failure on {r['case_id']}: {e}", file=sys.stderr)

    calib_df = pd.DataFrame(calib_rows)

    # ---- (g) structural stat: phase vs 3-digit occurrence-code prefix ----
    full = pd.read_parquet(ROOT / "data/processed/filtered.parquet")
    full = full[full["_event_year"].isin(cfg["splits"]["test_years"])]
    occ_col = cfg["fields"]["answer"]["occurrence_codes"]
    phase_col = cfg["fields"]["evidence"]["phase_of_flight"]
    struct = full.assign(_occ=full[occ_col].map(primary_code)).dropna(subset=["_occ", phase_col])
    struct = struct[struct[phase_col].astype(str).str.strip() != ""]
    struct["_prefix3"] = struct["_occ"].astype(str).str[:3]

    n_phase_vals = struct[phase_col].nunique()
    n_prefixes = struct["_prefix3"].nunique()
    phase_to_prefixes = struct.groupby(phase_col)["_prefix3"].nunique()
    prefix_to_phases = struct.groupby("_prefix3")[phase_col].nunique()
    phase_determ = (phase_to_prefixes == 1).mean()
    prefix_determ = (prefix_to_phases == 1).mean()

    # ---- print report ----
    print("=" * 70)
    print("ABLATION: phase_of_flight removed from evidence — 40-case one-shot")
    print("=" * 70)

    n = len(out_df)
    orig_top1 = out_df["orig_top1_correct"].mean() * 100
    orig_top3 = out_df["orig_top3_correct"].mean() * 100
    abl_top1 = out_df["abl_top1_correct"].mean() * 100
    abl_top3 = out_df["abl_top3_correct"].mean() * 100
    print(f"\nn = {n}")
    print(f"original  top-1 (Andy): {orig_top1:.1f}%   top-3 (Andy): {orig_top3:.1f}%")
    print(f"ablated   top-1 (this script): {abl_top1:.1f}%   top-3: {abl_top3:.1f}%")
    print(f"delta     top-1: {abl_top1 - orig_top1:+.1f} pts   top-3: {abl_top3 - orig_top3:+.1f} pts")

    n_changed = out_df["answer_changed"].sum()
    print(f"\nanswers changed (top-1 occurrence string, normalised): {n_changed} / {n}")
    if n_changed:
        chg = out_df[out_df["answer_changed"]]
        rw = ((chg["orig_top1_correct"]) & (~chg["abl_top1_correct"])).sum()
        wr = ((~chg["orig_top1_correct"]) & (chg["abl_top1_correct"])).sum()
        ww = ((~chg["orig_top1_correct"]) & (~chg["abl_top1_correct"])).sum()
        rr = ((chg["orig_top1_correct"]) & (chg["abl_top1_correct"])).sum()
        print(f"  right->wrong: {rw}   wrong->right: {wr}   wrong->wrong: {ww}   right->right: {rr}")

    print("\nsplit by has_narrative:")
    for flag, label in [(True, "WITH narrative"), (False, "WITHOUT narrative")]:
        d = out_df[out_df["has_narrative"] == flag]
        if len(d):
            print(f"  {label} (n={len(d)}): orig top-1 {d['orig_top1_correct'].mean()*100:.1f}%  "
                  f"abl top-1 {d['abl_top1_correct'].mean()*100:.1f}%  changed {d['answer_changed'].sum()}")

    print(f"\nabstentions — original: {out_df['orig_abstained'].sum()}   ablated: {out_df['abl_abstained'].sum()}")

    orig_cost = pd.to_numeric(orig["model_cost_usd"], errors="coerce").mean()
    abl_cost_mean = pd.to_numeric(out_df["abl_cost_usd"], errors="coerce").mean()
    print(f"\nmean cost/case USD — original: ${orig_cost:.4f}   ablated: ${abl_cost_mean:.4f}")

    print(f"\njudge calls made for this ablation: {n_judge_calls}  (failures: {n_judge_failures})")
    if judge_costs:
        print(f"judge mean cost/call USD: ${sum(judge_costs)/len(judge_costs):.4f}  total: ${sum(judge_costs):.4f}")

    print("\n" + "-" * 70)
    print("JUDGE CALIBRATION (judge run on all 40 ORIGINAL-run answers vs Andy)")
    print("-" * 70)
    if len(calib_df):
        agree1 = (calib_df["andy_top1"] == calib_df["judge_top1"]).mean() * 100
        agree3 = (calib_df["andy_top3"] == calib_df["judge_top3"]).mean() * 100
        print(f"n = {len(calib_df)}")
        print(f"top-1 agreement (Andy vs judge): {agree1:.1f}%")
        print("confusion (rows=Andy, cols=judge):")
        print(confusion(calib_df["andy_top1"], calib_df["judge_top1"]))
        print(f"\ntop-3 agreement (Andy vs judge): {agree3:.1f}%")
        print("confusion (rows=Andy, cols=judge):")
        print(confusion(calib_df["andy_top3"], calib_df["judge_top3"]))
        if calib_cost:
            print(f"\ncalibration judge mean cost/call USD: ${sum(calib_cost)/len(calib_cost):.4f}  total: ${sum(calib_cost):.4f}")
    else:
        print("no calibration rows produced (all judge calls failed)")

    print("\n" + "-" * 70)
    print("STRUCTURAL STAT: derived.phaseOfFlight vs 3-digit occurrence-code prefix")
    print(f"(test years {cfg['splits']['test_years']}, n={len(struct)} cases with both fields present)")
    print("-" * 70)
    print(f"distinct phase values: {n_phase_vals}")
    print(f"distinct 3-digit occurrence-code prefixes: {n_prefixes}")
    print(f"share of phase values mapping to a SINGLE unique 3-digit prefix: {phase_determ*100:.1f}%")
    print(f"share of 3-digit prefixes mapping to a SINGLE unique phase value: {prefix_determ*100:.1f}%")

    print(f"\nWrote {out_path}")
    print("REMINDER: that file is a MODEL'S opinion (transfer rule + LLM judge), not ground truth.")


if __name__ == "__main__":
    main()
