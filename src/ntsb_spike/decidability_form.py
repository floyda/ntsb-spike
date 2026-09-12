"""Session 6 — decidability scoring form: classify each miss by type and best-fix tool.

Usage:
    python -m ntsb_spike.decidability_form

Reads labelling/decidability.csv and writes labelling/decidability.html.
For each case, read the model's answer vs the NTSB's, and mark whether
it got the occurrence and top-3 correct. If wrong, assign a category
(A/B/C/D) and a tool that would fix it. Export downloads decidability.filled.csv
with all columns intact and the four human judgment columns filled.
Answers autosave to the browser's localStorage as you mark them.

Embeds the exact evidence payload the model saw: factual narrative plus
structured evidence fields. This allows judges to distinguish category A
(misread the evidence) from B/C/D (missing information).

Decodes NTSB occurrence and finding codes using labels from raw V2 records
(eventTier1Name — eventTier2Name, findingDescription).
"""
from __future__ import annotations

import glob
import html
import json

import pandas as pd
import yaml

from .common import ROOT, _extract_records
from .oneshot import build_evidence

LABELLING = ROOT / "labelling"
DATA_PROCESSED = ROOT / "data" / "processed"
RAW = ROOT / "data" / "raw"

PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Decidability scoring — model vs NTSB — 40 cases</title>
<style>
  :root { color-scheme: light dark; }
  body { font-family: system-ui, sans-serif; max-width: 54rem; margin: 2rem auto 6rem;
         padding: 0 1rem; line-height: 1.5; background: Canvas; color: CanvasText; }
  h1 { font-size: 1.3rem; margin-bottom: .5rem; }
  .legend { border: 1px solid color-mix(in srgb, CanvasText 20%, Canvas);
            border-radius: 8px; padding: 1rem 1.2rem; margin-bottom: 2rem;
            font-size: .9rem; line-height: 1.6; }
  .legend h2 { font-size: 1rem; margin: 0 0 .8rem 0; }
  .legend p { margin: .5rem 0; }
  .legend code { background: color-mix(in srgb, CanvasText 8%, Canvas);
                 padding: 0.15rem 0.3rem; border-radius: 3px; font-size: .85rem; }
  .category-desc { margin: .3rem 0 .3rem 1.5rem; font-size: .85rem; }
  .case { margin-top: 2rem; border: 1px solid color-mix(in srgb, CanvasText 20%, Canvas);
          border-radius: 8px; padding: 1rem 1.2rem; }
  .case h2 { font-size: 1rem; font-family: ui-monospace, monospace; margin: 0 0 .8rem; }
  .row { margin: .5rem 0; }
  .lbl { font-size: .75rem; text-transform: uppercase; letter-spacing: .05em; opacity: .7; }
  details { margin: .8rem 0; }
  details summary { cursor: pointer; font-weight: bold; font-size: .95rem; }
  .evidence { background: color-mix(in srgb, CanvasText 4%, Canvas); padding: .8rem;
              border-radius: 6px; margin-top: .5rem; }
  .narrative { white-space: pre-wrap; font-family: Georgia, serif; font-size: .9rem;
               line-height: 1.6; margin-bottom: .8rem; }
  .fields { font-size: .85rem; }
  .field { display: grid; grid-template-columns: 150px 1fr; gap: 1rem; margin: .3rem 0;
           padding: .2rem 0; }
  .field-key { font-weight: bold; opacity: .8; }
  .field-val { overflow-wrap: break-word; white-space: pre-wrap; }
  .model-block { margin: .8rem 0; }
  .answer { margin: .3rem 0 .8rem 0; }
  .model-cause { font-style: italic; color: CanvasText; }
  .model-top3 { font-size: .9rem; opacity: .85; }
  .top3-list { margin: .2rem 0 .2rem 0; padding-left: 1.6rem; }
  .top3-list li { margin: .1rem 0; }
  .model-meta { font-size: .8rem; opacity: .6; margin: .3rem 0; }
  .badge { display: inline-block; background: color-mix(in srgb, CanvasText 15%, Canvas);
           padding: 0.2rem 0.5rem; border-radius: 3px; font-size: .75rem;
           font-weight: bold; }
  .ntsb-block { background: color-mix(in srgb, CanvasText 7%, Canvas); padding: .8rem;
                border-radius: 6px; margin: .8rem 0; }
  .ntsb-block .lbl { display: block; margin-bottom: .2rem; }
  .finding-codes { font-size: .9rem; margin-top: .2rem; }
  .finding { margin: .2rem 0; }
  .choice-group { margin: 1rem 0; }
  .choice-group label { display: inline; font-weight: normal; margin-right: 1.2rem;
                        cursor: pointer; font-size: .95rem; }
  .select-group { margin: 1rem 0; }
  .select-group label { display: block; margin-bottom: .3rem; font-weight: bold;
                        font-size: .85rem; text-transform: uppercase; letter-spacing: .05em;
                        opacity: .7; }
  select { font: inherit; padding: .4rem; border-radius: 4px;
           border: 1px solid color-mix(in srgb, CanvasText 30%, Canvas);
           background: Canvas; color: CanvasText; }
  .bar { position: fixed; bottom: 0; left: 0; right: 0; background: Canvas;
         border-top: 1px solid color-mix(in srgb, CanvasText 25%, Canvas);
         padding: .6rem 1rem; display: flex; gap: 1rem; align-items: center;
         font-size: .9rem; }
  button { font: inherit; padding: .45rem 1rem; border-radius: 6px; cursor: pointer; }
</style>
</head>
<body>
<h1>Score the model's guesses</h1>
<div class="legend">
  <h2>How to work</h2>
  <p>For each case, read the <b>evidence the model saw</b> to judge category A ("misread it")
  vs B/C/D ("missing information"). Then compare the model's answer to the NTSB's.
  Mark whether it got the <b>occurrence correct</b> (exact match) and whether the right
  occurrence is in its <b>top 3</b>. If either is wrong, assign a <b>category</b>
  (what was missing?) and a <b>tool that would fix it</b>.</p>

  <p><b>Categories:</b></p>
  <div class="category-desc"><code>A</code> — the answer was in the evidence; the model misread it. Fix: better prompting.</div>
  <div class="category-desc"><code>B</code> — the model needed other parts of the same case (docket documents, aircraft history). Fix: fetch them.</div>
  <div class="category-desc"><code>C</code> — the model needed something outside this case (similar past accidents, weather report, a regulation). Fix: fetch it.</div>
  <div class="category-desc"><code>D</code> — not obtainable; the NTSB had physical evidence we don't have. No fix.</div>

  <p><b>Tools (for C cases only):</b> <code>precedent</code> (similar accident history),
  <code>weather</code> (historical METAR/weather report),
  <code>history</code> (aircraft maintenance/incident history),
  <code>docket</code> (case documents and reports),
  <code>regulation</code> (FAA rules and guidance).</p>

  <p>Judge generously on wording, strictly on substance. Leave category and tool blank on cases
  the model got right. Marks autosave; export when done.</p>
</div>
__CASES__
<div class="bar">
  <span id="progress"></span>
  <button onclick="exportCsv()">Export decidability.filled.csv</button>
</div>
<script>
const DATA = __DATA__;
const KEY = "decidability-v1";
const saved = JSON.parse(localStorage.getItem(KEY) || "{}");

function radioVal(i, f) {
  const el = document.querySelector(`input[name=c${i}_${f}]:checked`);
  return el ? el.value : "";
}

function save() {
  const out = {};
  DATA.forEach((c, i) => {
    const occ = radioVal(i, "occ");
    const top3 = radioVal(i, "top3");
    const cat = radioVal(i, "cat");
    const tool = document.getElementById(`c${i}_tool`).value;
    if (occ || top3 || cat || tool) {
      out[c.case_id] = { occ, top3, cat, tool };
    }
  });
  localStorage.setItem(KEY, JSON.stringify(out));
  const done = Object.keys(out).length;
  document.getElementById("progress").textContent = `${done} / ${DATA.length} cases marked`;
}

window.addEventListener("change", save);
window.addEventListener("DOMContentLoaded", () => {
  DATA.forEach((c, i) => {
    const s = saved[c.case_id] || {};
    [["occ", s.occ], ["top3", s.top3], ["cat", s.cat]].forEach(([f, v]) => {
      if (v) {
        const el = document.querySelector(`input[name=c${i}_${f}][value="${v}"]`);
        if (el) el.checked = true;
      }
    });
    if (s.tool) document.getElementById(`c${i}_tool`).value = s.tool;
  });
  save();
});

function q(v) { return '"' + String(v ?? "").replace(/"/g, '""') + '"'; }

function exportCsv() {
  const marks = JSON.parse(localStorage.getItem(KEY) || "{}");
  if (Object.keys(marks).length < DATA.length && !confirm("Not all cases marked — export anyway?")) return;

  const header = "case_id,ntsb_occurrence,ntsb_finding_codes,ntsb_probable_cause,model_occurrence,model_top3,model_finding_codes,model_probable_cause,model_confidence,model_abstained,occurrence_correct,top3_correct,category,tool_that_would_fix_it,model_cost_usd";
  const rows = DATA.map(c => {
    const m = marks[c.case_id] || {};
    return [
      c.case_id,
      c.ntsb_occurrence,
      c.ntsb_finding_codes,
      c.ntsb_probable_cause,
      c.model_occurrence,
      c.model_top3,
      c.model_finding_codes,
      c.model_probable_cause,
      c.model_confidence,
      c.model_abstained,
      m.occ ?? "",
      m.top3 ?? "",
      m.cat ?? "",
      m.tool ?? "",
      c.model_cost_usd,
    ].map(q).join(",");
  });
  const blob = new Blob([header + "\\n" + rows.join("\\n") + "\\n"], { type: "text/csv" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "decidability.filled.csv";
  a.click();
}
</script>
</body>
</html>
"""

CASE = """<div class="case">
<h2>{n}/40 — {case_id}</h2>

<details open>
  <summary>Evidence the model saw</summary>
  <div class="evidence">
    {evidence_html}
  </div>
</details>

<div class="model-block">
  <div class="lbl">Model's answer</div>
  <div class="answer">
    <div class="model-cause">{model_cause}</div>
    <div class="model-top3">top-3:<ol class="top3-list">{model_top3}</ol></div>
    <div class="model-meta">confidence: {model_conf}{model_abstained}</div>
    <div class="model-meta">finding codes:</div>
    <div class="finding-codes">{model_codes}</div>
  </div>
</div>

<div class="ntsb-block">
  <div class="lbl">NTSB's answer</div>
  <div class="row" style="margin: .5rem 0;"><strong>{ntsb_cause}</strong></div>
  <div class="row" style="margin: .5rem 0; font-size: .9rem;">occurrence: {ntsb_occ}</div>
  <div class="row" style="margin: .5rem 0; font-size: .9rem;">{ntsb_findings}</div>
</div>

<div class="choice-group">
  <label><input type="radio" name="c{i}_occ" id="c{i}_occ_1" value="1"> occurrence correct</label>
  <label><input type="radio" name="c{i}_occ" id="c{i}_occ_0" value="0"> occurrence wrong</label>
</div>

<div class="choice-group">
  <label><input type="radio" name="c{i}_top3" id="c{i}_top3_1" value="1"> top-3 correct</label>
  <label><input type="radio" name="c{i}_top3" id="c{i}_top3_0" value="0"> top-3 wrong</label>
</div>

<div class="choice-group">
  <label><input type="radio" name="c{i}_cat" id="c{i}_cat_a" value="A"> A</label>
  <label><input type="radio" name="c{i}_cat" id="c{i}_cat_b" value="B"> B</label>
  <label><input type="radio" name="c{i}_cat" id="c{i}_cat_c" value="C"> C</label>
  <label><input type="radio" name="c{i}_cat" id="c{i}_cat_d" value="D"> D</label>
  <label><input type="radio" name="c{i}_cat" id="c{i}_cat_none" value=""> —</label>
</div>

<div class="select-group">
  <label for="c{i}_tool">If C: which tool?</label>
  <select id="c{i}_tool">
    <option value=""></option>
    <option value="precedent">precedent</option>
    <option value="weather">weather</option>
    <option value="history">history</option>
    <option value="docket">docket</option>
    <option value="regulation">regulation</option>
  </select>
</div>
</div>"""


def build_code_lookups() -> tuple[dict[str, str], dict[str, str]]:
    """Scan raw JSON files and build eventCode and findingCode label lookups.

    Returns:
        (event_codes dict, finding_codes dict) where keys are code strings
        and values are human-readable labels.
    """
    event_codes = {}  # eventCode → "eventTier1Name — eventTier2Name"
    finding_codes = {}  # findingCode → findingDescription

    files = sorted(glob.glob(str(RAW / "**" / "cases_*.json"), recursive=True))
    for fp in files:
        with open(fp) as f:
            payload = json.load(f)
        records = _extract_records(payload)

        for record in records:
            # Extract event codes and labels
            aircrafts = record.get("aircrafts")
            if isinstance(aircrafts, list):
                for aircraft in aircrafts:
                    events = aircraft.get("events")
                    if isinstance(events, list):
                        for event in events:
                            code = event.get("eventCode")
                            tier1 = event.get("eventTier1Name", "").strip()
                            tier2 = event.get("eventTier2Name", "").strip()
                            if code and (tier1 or tier2):
                                label = f"{tier1} — {tier2}" if tier1 and tier2 else (tier1 or tier2)
                                event_codes[str(code)] = label

                    # Extract finding codes and descriptions
                    findings = aircraft.get("findings")
                    if isinstance(findings, list):
                        for finding in findings:
                            code = finding.get("findingCode")
                            desc = finding.get("findingDescription")
                            if code and desc:
                                desc_str = str(desc).strip()
                                if desc_str:
                                    finding_codes[str(code)] = desc_str

    return event_codes, finding_codes


def format_evidence_html(evidence: dict) -> str:
    """Format evidence dict as readable HTML: narrative as paragraphs, fields as definition list."""
    if not evidence:
        return '<div style="opacity: .6; font-style: italic;">No evidence available</div>'

    html_parts = []

    # Display factual_narrative first, as readable paragraphs
    narrative = evidence.pop("factual_narrative", "").strip()
    if narrative:
        # Split on double newlines to preserve paragraph breaks
        paragraphs = narrative.split("\n\n")
        html_parts.append('<div class="narrative">')
        for para in paragraphs:
            if para.strip():
                html_parts.append(html.escape(para.strip()))
                html_parts.append("\n\n")
        html_parts.append("</div>")
    else:
        html_parts.append('<div style="opacity: .6; font-size: .9rem; margin-bottom: .5rem;">'
                         '(no factual narrative)</div>')

    # Display remaining fields as a compact definition list
    if evidence:
        html_parts.append('<div class="fields">')
        for key, val in sorted(evidence.items()):
            if val is not None and str(val).strip():
                # Clean up JSON stringified values for readability
                val_str = str(val)
                if val_str.startswith('"') and val_str.endswith('"'):
                    val_str = json.loads(val_str)
                html_parts.append(
                    f'<div class="field"><div class="field-key">{html.escape(key)}:</div>'
                    f'<div class="field-val">{html.escape(str(val_str))}</div></div>'
                )
        html_parts.append("</div>")

    return "".join(html_parts)


def format_ntsb_occurrence(code: str, event_codes: dict[str, str]) -> str:
    """Format NTSB occurrence code with label if available."""
    label = event_codes.get(code)
    if label:
        return f"{html.escape(code)} — {html.escape(label)}"
    else:
        return f"{html.escape(code)} (no label found)"


def format_ntsb_findings(codes_str: str, finding_codes: dict[str, str]) -> str:
    """Format NTSB finding codes with labels if available."""
    if not codes_str or codes_str == "[]":
        return "finding codes: (none)"

    # Parse the codes from the CSV representation
    try:
        # The CSV stores finding codes as a string representation of a list
        # e.g., "['0106203721' '0206300044' ...]"
        codes_str_clean = codes_str.strip("[]'\" ")
        codes = [c.strip("'\" ") for c in codes_str_clean.split()]
    except Exception:
        # Fallback if parsing fails
        return f"finding codes: {html.escape(codes_str)}"

    if not codes:
        return "finding codes: (none)"

    html_parts = ['<span style="display: block; margin-top: .3rem;">finding codes:</span>']
    html_parts.append('<div class="finding-codes">')
    for code in codes:
        desc = finding_codes.get(code)
        if desc:
            html_parts.append(
                f'<div class="finding">{html.escape(code)} — {html.escape(desc)}</div>'
            )
        else:
            html_parts.append(f'<div class="finding">{html.escape(code)} (no label found)</div>')
    html_parts.append("</div>")
    return "".join(html_parts)


def main() -> None:
    # Load config and build code lookups
    with open(ROOT / "config.yaml") as f:
        cfg = yaml.safe_load(f)

    print("Building code lookups from raw JSON files...")
    event_codes, finding_codes = build_code_lookups()
    print(f"  Event codes: {len(event_codes)} unique labels")
    print(f"  Finding codes: {len(finding_codes)} unique labels")

    # Load parquet data
    parquet_path = DATA_PROCESSED / "filtered.parquet"
    parquet_df = pd.read_parquet(parquet_path)

    # Load decidability CSV
    dec_df = pd.read_csv(LABELLING / "decidability.csv", dtype=str).fillna("")

    # Build cases HTML with embedded evidence
    cases_html_parts = []
    empty_narrative_count = 0
    unresolved_codes = set()

    for i, r in enumerate(dec_df.itertuples()):
        # Match case in parquet by ntsbNumber (which is the case_id)
        matching_rows = parquet_df[parquet_df["ntsbNumber"] == r.case_id]
        evidence_html = ""

        if len(matching_rows) > 0:
            parquet_row = matching_rows.iloc[0]
            evidence = build_evidence(cfg, parquet_row)
            if not evidence.get("factual_narrative"):
                empty_narrative_count += 1
            evidence_html = format_evidence_html(evidence.copy())
        else:
            evidence_html = '<div style="opacity: .6; font-style: italic;">Case not found in data</div>'

        # Format NTSB occurrence and findings with labels
        ntsb_occ = format_ntsb_occurrence(r.ntsb_occurrence, event_codes)
        if r.ntsb_occurrence not in event_codes:
            unresolved_codes.add(("event", r.ntsb_occurrence))

        ntsb_findings_html = format_ntsb_findings(r.ntsb_finding_codes, finding_codes)
        # Track unresolved finding codes
        try:
            codes_str_clean = r.ntsb_finding_codes.strip("[]'\" ")
            codes = [c.strip("'\" ") for c in codes_str_clean.split()]
            for code in codes:
                if code and code not in finding_codes:
                    unresolved_codes.add(("finding", code))
        except Exception:
            pass

        cases_html_parts.append(
            CASE.format(
                n=i + 1,
                i=i,
                case_id=html.escape(r.case_id),
                evidence_html=evidence_html,
                model_cause=html.escape(r.model_probable_cause),
                model_top3="".join(
                    f"<li>{html.escape(t.strip())}</li>"
                    for t in r.model_top3.split("|") if t.strip()
                ) or "<li>(none)</li>",
                model_conf=html.escape(r.model_confidence),
                model_codes="".join(
                    f'<div class="finding">{html.escape(c.strip())}</div>'
                    for c in r.model_finding_codes.split("|") if c.strip()
                ) or '<div class="finding">(none)</div>',
                model_abstained=" | abstained" if r.model_abstained == "True" else "",
                ntsb_cause=html.escape(r.ntsb_probable_cause),
                ntsb_occ=ntsb_occ,
                ntsb_findings=ntsb_findings_html,
            )
        )

    cases_html = "\n".join(cases_html_parts)

    data = json.dumps([
        {
            "case_id": r.case_id,
            "ntsb_occurrence": r.ntsb_occurrence,
            "ntsb_finding_codes": r.ntsb_finding_codes,
            "ntsb_probable_cause": r.ntsb_probable_cause,
            "model_occurrence": r.model_occurrence,
            "model_top3": r.model_top3,
            "model_finding_codes": r.model_finding_codes,
            "model_probable_cause": r.model_probable_cause,
            "model_confidence": r.model_confidence,
            "model_abstained": r.model_abstained,
            "model_cost_usd": r.model_cost_usd,
        }
        for r in dec_df.itertuples()
    ])

    out = LABELLING / "decidability.html"
    out.write_text(PAGE.replace("__CASES__", cases_html).replace("__DATA__", data))
    print(f"\nWrote {out} ({len(dec_df)} cases).")
    print(f"Cases with empty factual_narrative: {empty_narrative_count} / {len(dec_df)}")
    print(f"Unresolved codes: {len(unresolved_codes)}")
    if unresolved_codes:
        print(f"  Unresolved: {unresolved_codes}")
    print(f"Open in a browser, read the evidence, mark occurrence/top3/category/tool, export.")


if __name__ == "__main__":
    main()
