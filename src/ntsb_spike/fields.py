"""Session 1 — field completeness and narrative length statistics.

Usage:
    python -m ntsb_spike.fields
"""
from __future__ import annotations

import pandas as pd
import tiktoken

from .common import apply_filters, load_config, load_raw_frame, save_processed


def token_len(text: str, enc) -> int:
    return len(enc.encode(text)) if isinstance(text, str) else 0


def main() -> None:
    cfg = load_config()
    df = apply_filters(load_raw_frame(), cfg)
    roles = {**cfg["fields"]["evidence"], **cfg["fields"]["answer"]}
    rows = []
    for role, col in roles.items():
        if not col:
            rows.append((role, "(unmapped)", None))
            continue
        present = df[col].notna() & (df[col].astype(str).str.strip() != "")
        rows.append((role, col, round(100 * present.mean(), 1)))
    table = pd.DataFrame(rows, columns=["role", "field", "% present"])
    print(f"n = {len(df)} cases after filters\n")
    print(table.to_string(index=False))

    # A2: both probable cause and codes present
    pc = cfg["fields"]["answer"]["probable_cause"]
    occ = cfg["fields"]["answer"]["occurrence_codes"]
    if pc and occ:
        both = df[pc].notna() & df[occ].notna()
        print(f"\nA2: probable cause AND occurrence codes present: {100 * both.mean():.1f}%  (kill if < 80%)")

    fact = cfg["fields"]["evidence"]["factual_narrative"]
    if fact:
        enc = tiktoken.get_encoding("cl100k_base")
        lengths = df[fact].map(lambda t: token_len(t, enc))
        print("\nFactual narrative length (tokens):")
        print(lengths.describe(percentiles=[0.25, 0.5, 0.75, 0.95]).round(0).to_string())
        df["_factual_tokens"] = lengths
    print(f"\nSaved → {save_processed(df, 'filtered')}")


if __name__ == "__main__":
    main()
