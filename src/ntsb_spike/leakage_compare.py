"""Session 4 — side-by-side scoring form: your guess vs the NTSB's probable cause.

Usage:
    python -m ntsb_spike.leakage_compare

Reads labelling/leakage.filled.csv and labelling/leakage.KEY.csv, writes
labelling/leakage_compare.html. For each case, mark whether your guess named
the same cause (right / wrong). Export downloads leakage.filled.csv with the
`correct` column appended — replace the one in labelling/ and rerun
`python -m ntsb_spike.leakage score`.
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
<title>Leakage scoring — guess vs verdict</title>
<style>
  :root { color-scheme: light dark; }
  body { font-family: system-ui, sans-serif; max-width: 50rem; margin: 2rem auto 6rem;
         padding: 0 1rem; line-height: 1.5; background: Canvas; color: CanvasText; }
  .case { margin-top: 2rem; border: 1px solid color-mix(in srgb, CanvasText 20%, Canvas);
          border-radius: 8px; padding: 1rem 1.2rem; }
  .case h2 { font-size: 1rem; font-family: ui-monospace, monospace; margin: 0 0 .6rem; }
  .row { margin: .5rem 0; }
  .lbl { font-size: .75rem; text-transform: uppercase; letter-spacing: .05em; opacity: .7; }
  .guess { font-style: italic; }
  .verdict { background: color-mix(in srgb, CanvasText 7%, Canvas); padding: .5rem .8rem; border-radius: 6px; }
  .conf { opacity: .7; font-size: .85rem; }
  .choice label { display: inline; font-weight: normal; margin-right: 1.2rem; cursor: pointer; }
  .bar { position: fixed; bottom: 0; left: 0; right: 0; background: Canvas;
         border-top: 1px solid color-mix(in srgb, CanvasText 25%, Canvas);
         padding: .6rem 1rem; display: flex; gap: 1rem; align-items: center; font-size: .9rem; }
  button { font: inherit; padding: .45rem 1rem; border-radius: 6px; cursor: pointer; }
</style>
</head>
<body>
<h1>Score your guesses</h1>
<p>Judge generously on wording, strictly on substance: mark <b>right</b> if your guess
names the same primary cause the NTSB did (e.g. "carb ice" vs "loss of engine power due
to carburetor icing"), <b>wrong</b> if it names a different mechanism or misses the
primary cause. Marks autosave; export when done.</p>
__CASES__
<div class="bar">
  <span id="progress"></span>
  <button onclick="exportCsv()">Export leakage.filled.csv (with correct column)</button>
</div>
<script>
const DATA = __DATA__;
const KEY = "leakage-compare-v1";
const saved = JSON.parse(localStorage.getItem(KEY) || "{}");
function save() {
  const out = {};
  DATA.forEach((c, i) => {
    const v = document.querySelector(`input[name=c${i}]:checked`);
    if (v) out[c.case_id] = v.value;
  });
  localStorage.setItem(KEY, JSON.stringify(out));
  document.getElementById("progress").textContent =
    `${Object.keys(out).length} / ${DATA.length} marked`;
}
window.addEventListener("change", save);
window.addEventListener("DOMContentLoaded", () => {
  DATA.forEach((c, i) => {
    if (saved[c.case_id] !== undefined) {
      const el = document.querySelector(`input[name=c${i}][value="${saved[c.case_id]}"]`);
      if (el) el.checked = true;
    }
  });
  save();
});
function q(v) { return '"' + String(v ?? "").replace(/"/g, '""') + '"'; }
function exportCsv() {
  const marks = JSON.parse(localStorage.getItem(KEY) || "{}");
  if (Object.keys(marks).length < DATA.length && !confirm("Not all cases marked — export anyway?")) return;
  const header = "case_id,factual_account,your_guess_at_cause,your_confidence_0_to_1,sentences_that_state_a_conclusion,correct";
  const rows = DATA.map(c => [
    c.case_id, c.factual_account, c.guess, c.conf, c.sentences, marks[c.case_id] ?? "",
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
<h2>{n}/{total} — {case_id}</h2>
<div class="row"><div class="lbl">Your guess (confidence {conf})</div>
<div class="guess">{guess}</div></div>
<div class="row"><div class="lbl">NTSB probable cause</div>
<div class="verdict">{cause}</div></div>
<div class="row choice">
<label><input type="radio" name="c{i}" value="1"> right</label>
<label><input type="radio" name="c{i}" value="0"> wrong</label>
</div>
</div>"""


def main() -> None:
    filled = pd.read_csv(LABELLING / "leakage.filled.csv", dtype=str).fillna("")
    key = pd.read_csv(LABELLING / "leakage.KEY.csv", dtype=str).fillna("")
    m = filled.merge(key[["case_id", "probable_cause"]], on="case_id")
    cases_html = "\n".join(
        CASE.format(n=i + 1, total=len(m), i=i,
                    case_id=html.escape(r.case_id),
                    conf=html.escape(r.your_confidence_0_to_1 or "?"),
                    guess=html.escape(r.your_guess_at_cause or "(no guess)"),
                    cause=html.escape(r.probable_cause))
        for i, r in enumerate(m.itertuples())
    )
    data = json.dumps([
        {"case_id": r.case_id, "factual_account": r.factual_account,
         "guess": r.your_guess_at_cause, "conf": r.your_confidence_0_to_1,
         "sentences": r.sentences_that_state_a_conclusion}
        for r in m.itertuples()
    ])
    out = LABELLING / "leakage_compare.html"
    out.write_text(PAGE.replace("__CASES__", cases_html).replace("__DATA__", data))
    print(f"Wrote {out} ({len(m)} cases). Open in a browser, mark right/wrong, export, "
          "replace labelling/leakage.filled.csv, rerun `leakage score`.")


if __name__ == "__main__":
    main()
