"""Session 0 — print every field of one case, marking structured vs free text.

Usage:
    python -m ntsb_spike.inspect_record            # first record
    python -m ntsb_spike.inspect_record <case_id>  # a specific one (needs fields.id set)
"""
from __future__ import annotations

import sys

from .common import load_config, load_raw_frame


def classify(value) -> str:
    if isinstance(value, str) and len(value) > 200:
        return "FREE TEXT"
    if isinstance(value, list):
        return "LIST"
    if isinstance(value, dict):
        return "NESTED"
    return "structured"


def main() -> None:
    cfg = load_config()
    df = load_raw_frame()
    if len(sys.argv) > 1 and cfg["fields"]["id"]:
        row = df[df[cfg["fields"]["id"]].astype(str) == sys.argv[1]].iloc[0]
    else:
        row = df.iloc[0]
    width = max(len(c) for c in df.columns)
    for col in df.columns:
        v = row[col]
        kind = classify(v)
        preview = (str(v)[:90] + "…") if isinstance(v, str) and len(v) > 90 else v
        print(f"{col:<{width}}  [{kind:<10}]  {preview}")
    print(f"\n{len(df.columns)} fields. Now fill fields.* in config.yaml.")


if __name__ == "__main__":
    main()
