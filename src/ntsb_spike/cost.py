"""Session 5 — token counts and cost estimate.

Usage:
    python -m ntsb_spike.cost
"""
from __future__ import annotations

import json

import pandas as pd
import tiktoken

from .common import load_config
from .oneshot import build_evidence


def main() -> None:
    cfg = load_config()
    df = pd.read_parquet("data/processed/filtered.parquet")
    enc = tiktoken.get_encoding("cl100k_base")
    lengths = df["_factual_tokens"] if "_factual_tokens" in df else None
    if lengths is None:
        raise SystemExit("Run fields.py first (it computes narrative token lengths).")
    median_case = df.iloc[(lengths - lengths.median()).abs().argsort().iloc[0]]
    long_case = df.iloc[lengths.idxmax() if lengths.index.equals(df.index) else lengths.argmax()]

    m = cfg["model"]
    out_tokens = 300  # structured answer, codes, one-sentence cause, confidence
    rows = []
    for label, case in (("typical", median_case), ("long", long_case)):
        ev = build_evidence(cfg, case)
        n_in = len(enc.encode(json.dumps(ev, default=lambda o: o.tolist() if hasattr(o, "tolist") else str(o))))
        cost = (n_in * m["input_cost_per_mtok_gbp"] + out_tokens * m["output_cost_per_mtok_gbp"]) / 1_000_000
        rows.append((label, n_in, out_tokens, round(cost, 4)))
    t = pd.DataFrame(rows, columns=["case", "tokens_in", "tokens_out", "gbp_per_call"])
    print(t.to_string(index=False))

    typical = t.loc[t["case"] == "typical", "gbp_per_call"].iloc[0]
    n_test = 3000
    ablations = 4  # no-similar, no-weather, no-docket, no-history
    print(f"\nFull held-out run ({n_test} cases): £{typical * n_test:.2f}")
    print(f"With {ablations} ablations: £{typical * n_test * (1 + ablations):.2f}")
    print(f"\nA7: £{typical:.4f} per case  {'✅' if typical < 0.05 else '⚠️ over £0.05 — plan to sample'}")
    print("\nNote: an agent run costs more than one-shot (several tool calls, retrieved precedents).")
    print("Multiply by ~3–5 for a realistic agent estimate.")


if __name__ == "__main__":
    main()
