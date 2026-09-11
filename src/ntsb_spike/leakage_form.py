"""Session 4 — render labelling/leakage.csv as a readable HTML labelling form.

Usage:
    python -m ntsb_spike.leakage_form

Writes labelling/leakage.html. Open it in a browser, work through the 30 cases
blind (guess the cause, give a 0-1 confidence, paste any conclusion-stating
sentences), then click "Export filled CSV" — it downloads leakage.filled.csv,
which you move into labelling/ and score with `python -m ntsb_spike.leakage score`.
Answers autosave to the browser's localStorage as you type.
"""
from __future__ import annotations

import html
import json

import pandas as pd

from .common import ROOT

LABELLING = ROOT / "labelling"

PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Leakage labelling — 30 cases</title>
<style>
  :root { color-scheme: light dark; }
  body { font-family: Georgia, 'Times New Roman', serif; max-width: 46rem;
         margin: 2rem auto 6rem; padding: 0 1rem; line-height: 1.55;
         background: Canvas; color: CanvasText; }
  h1 { font-size: 1.4rem; } .rules { border: 1px solid color-mix(in srgb, CanvasText 25%, Canvas);
         padding: .8rem 1rem; border-radius: 8px; font-size: .95rem; }
  .case { margin-top: 3rem; border-top: 3px double color-mix(in srgb, CanvasText 40%, Canvas); padding-top: 1rem; }
  .case h2 { font-size: 1.05rem; font-family: ui-monospace, monospace; }
  .account { white-space: pre-wrap; background: color-mix(in srgb, CanvasText 6%, Canvas);
         padding: 1rem 1.2rem; border-radius: 8px; }
  label { display: block; margin-top: .9rem; font-weight: bold; font-family: system-ui, sans-serif; font-size: .85rem; }
  textarea, input { width: 100%; box-sizing: border-box; font: inherit; font-size: .95rem;
         padding: .5rem; border: 1px solid color-mix(in srgb, CanvasText 30%, Canvas);
         border-radius: 6px; background: Canvas; color: CanvasText; }
  textarea { min-height: 3.2rem; resize: vertical; }
  input[type=number] { width: 8rem; }
  .bar { position: fixed; bottom: 0; left: 0; right: 0; background: Canvas;
         border-top: 1px solid color-mix(in srgb, CanvasText 25%, Canvas);
         padding: .6rem 1rem; display: flex; gap: 1rem; align-items: center;
         font-family: system-ui, sans-serif; font-size: .9rem; }
  button { font: inherit; padding: .45rem 1rem; border-radius: 6px; cursor: pointer; }
</style>
</head>
<body>
<h1>Leakage labelling — 30 factual accounts</h1>
<div class="rules">
  For each case, <b>before anything else</b>: read the account, write one line saying what
  you think caused the accident, and how sure you are (0–1). Then paste (verbatim) any
  sentences that state or strongly imply a <i>conclusion</i> rather than a fact
  ("failed to…", "inadequate…", "improperly…"). Do not look anything up.
  Do not open <code>leakage.KEY.csv</code> until you have exported.
  Answers autosave in this browser; click <b>Export filled CSV</b> when done.
</div>
__CASES__
<div class="bar">
  <span id="progress"></span>
  <button onclick="exportCsv()">Export filled CSV</button>
  <button onclick="if(confirm('Clear all saved answers?')){localStorage.removeItem(KEY);location.reload()}">Reset</button>
</div>
<script>
const DATA = __DATA__;
const KEY = "leakage-labelling-v1";
const saved = JSON.parse(localStorage.getItem(KEY) || "{}");
function fieldId(i, f) { return `c${i}_${f}`; }
function save() {
  const out = {};
  DATA.forEach((c, i) => {
    out[c.case_id] = {
      guess: document.getElementById(fieldId(i, "guess")).value,
      conf: document.getElementById(fieldId(i, "conf")).value,
      sentences: document.getElementById(fieldId(i, "sent")).value,
    };
  });
  localStorage.setItem(KEY, JSON.stringify(out));
  const done = Object.values(out).filter(v => v.guess.trim() !== "").length;
  document.getElementById("progress").textContent = `${done} / ${DATA.length} guessed`;
}
window.addEventListener("input", save);
window.addEventListener("DOMContentLoaded", () => {
  DATA.forEach((c, i) => {
    const s = saved[c.case_id] || {};
    document.getElementById(fieldId(i, "guess")).value = s.guess || "";
    document.getElementById(fieldId(i, "conf")).value = s.conf || "";
    document.getElementById(fieldId(i, "sent")).value = s.sentences || "";
  });
  save();
});
function q(v) { return '"' + String(v ?? "").replace(/"/g, '""') + '"'; }
function exportCsv() {
  const header = "case_id,factual_account,your_guess_at_cause,your_confidence_0_to_1,sentences_that_state_a_conclusion";
  const rows = DATA.map((c, i) => [
    c.case_id, c.factual_account,
    document.getElementById(fieldId(i, "guess")).value,
    document.getElementById(fieldId(i, "conf")).value,
    document.getElementById(fieldId(i, "sent")).value,
  ].map(q).join(","));
  const blob = new Blob([header + "\\n" + rows.join("\\n") + "\\n"], { type: "text/csv" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "leakage.filled.csv";
  a.click();
}
</script>
</body>
</html>
"""

CASE = """<div class="case">
<h2>Case {n} of {total} — {case_id}</h2>
<div class="account">{account}</div>
<label for="c{i}_guess">Your guess at the cause (one line)</label>
<textarea id="c{i}_guess"></textarea>
<label for="c{i}_conf">Confidence 0–1</label>
<input id="c{i}_conf" type="number" min="0" max="1" step="0.1">
<label for="c{i}_sent">Sentences that state a conclusion (verbatim; blank if none)</label>
<textarea id="c{i}_sent"></textarea>
</div>"""


def main() -> None:
    df = pd.read_csv(LABELLING / "leakage.csv")
    cases_html = "\n".join(
        CASE.format(n=i + 1, total=len(df), i=i,
                    case_id=html.escape(str(r.case_id)),
                    account=html.escape(str(r.factual_account)))
        for i, r in enumerate(df.itertuples())
    )
    data = json.dumps(
        [{"case_id": str(r.case_id), "factual_account": str(r.factual_account)} for r in df.itertuples()]
    )
    out = LABELLING / "leakage.html"
    out.write_text(PAGE.replace("__CASES__", cases_html).replace("__DATA__", data))
    print(f"Wrote {out} — open it in a browser; export produces leakage.filled.csv.")


if __name__ == "__main__":
    main()
