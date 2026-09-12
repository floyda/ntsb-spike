# Prompts for running the spike with a coding agent

Use these with Claude Code (or similar) from the repo root. Each block is one goal.
Stop points are where the agent hands back to you.

## /goal — Session 0: access viability

```
Read CLAUDE.md, docs/spike-plan.md (Session 0) and docs/session-0-checklist.md.

Goal: get one real month of closed NTSB general-aviation cases into data/raw/ via the
documented API, and fill config.yaml from what you actually observe.

Do, in order:
1. Locate the current NTSB documentation for the case-query API (CAROL /
   GetCasesByDateRangeV2) and the 2027 migration notice. Quote the URLs you used.
   If you cannot find authoritative docs, stop and report — do not guess.
2. Fill config.yaml `api:` from the docs. Update fetch.py TODOs to match.
3. Fetch one month of 2022 events. Save the raw response verbatim.
4. Run inspect_record.py on one case. From the output, fill config.yaml `fields:`.
   For each field you map, note in the session log why you assigned it to evidence
   or answer. Leave anything ambiguous unmapped and list it.
5. Attempt to open the public docket for that case. Report whether documents can be
   listed and fetched programmatically.
6. Download avall.zip as the fallback and list its table names.
7. Fill A1 and A9 in docs/assumptions.md with evidence. Write the Session 0 log entry.

STOP. Report the field mapping and any unmapped fields for Andy to confirm before Session 1.
```

## /goal — Sessions 1 and 2: completeness and volume

```
Read CLAUDE.md and docs/spike-plan.md (Sessions 1 and 2). config.yaml has been confirmed.

Goal: real completeness percentages and volume/time-to-close numbers.

1. Widen the fetch to three months of 2022 if the API allows it cheaply.
2. Resolve the closed/GA filter TODOs in common.apply_filters() from real field values.
   Show me the distinct values you filtered on.
3. Run fields.py. Fill A2, A3, A12 in the assumptions register.
   For A3, state explicitly whether factual / analysis / probable cause are separate fields.
   For A12, read 20 accounts and report whether any personal names appear.
4. Check A8: does any record carry preliminary-report text or a version history? Time-box 15 min.
5. Run volume.py. Fill A11 with the time-to-close percentiles.
6. Write the log entries for Sessions 1 and 2.

STOP. Report the completeness table and the time-to-close numbers.
```

## /goal — Session 4 prep, then Session 3 (this order is deliberate)

```
Read CLAUDE.md and docs/spike-plan.md (Sessions 4 and 3).

Goal: prepare the leakage sheet for Andy, run the automated leakage scan, then the baselines.

1. Run `leakage.py sheet`. Do not open or read leakage.KEY.csv. Do not fill the sheet.
2. Run `leakage.py scan`. Report the give-away phrase rate and the structured-field purity
   table. For any evidence field where most values map to exactly one occurrence code,
   recommend moving it to `fields.answer` and explain.
3. OPTIONAL, clearly labelled: produce labelling/leakage.model.csv in which you guess the
   cause from the factual account alone, for the same 30 cases. This is a model-side leakage
   signal to sit next to Andy's, not a substitute for it.

STOP. Andy fills leakage.csv blind, runs `leakage.py score`, and decides which fields move
to answer. Only then:

4. Run baseline.py, conditioning only on fields still in `fields.evidence`.
5. Fill A4 and A5 in the assumptions register. Write the log entries.

STOP. Report the baseline table and the class-imbalance number.
```

## /goal — Sessions 5 and 6: cost and one-shot ceiling

```
Read CLAUDE.md and docs/spike-plan.md (Sessions 5 and 6).

Goal: cost per case, tool feasibility, and the one-shot ceiling sheet.

1. Fill config.yaml `model:` with a small, cheap model and its current per-token prices
   from the provider's pricing page (cite it).
2. Run cost.py. Fill A7.
3. Test the two external tools: fetch one historical METAR from the Iowa Mesonet ASOS
   archive for the station/time named in one account; extract text from one docket PDF.
   Fill A10 and A9 (update). Report extraction quality honestly.
4. Run `oneshot.py --dry` and confirm the leakage assertion passes.
5. Run oneshot.py for real on the 40-case stratified sample.
6. Write the log entries.

STOP. Andy fills the last four columns of labelling/decidability.csv. Do not fill them.
After he has: run decidability.py and fill A6.
```

## /goal — Session 7: decision and report

```
Read CLAUDE.md, docs/spike-plan.md (Session 7 and the decision rule), docs/assumptions.md
and docs/session-log.md.

Goal: apply the decision rule mechanically and draft the spike report.

1. Apply the decision rule from spike-plan.md to the filled assumptions register.
   State which branch it lands on and which three numbers decided it. If it is the grey
   zone, list the C cases from decidability.filled.csv and characterise them.
2. Draft docs/spike-report.md from docs/spike-report-template.md. Every number must be
   traceable to a script or a labelling sheet; cite which.
3. List the surprises from the session log in section 8.
4. Do not soften a negative result. If the answer is "classifier" or "stop", say so in
   the first line.

STOP. Andy reviews and edits the report; the decision is his.
```

## /goal — Post-spike: from report to build brief

```
Read CLAUDE.md, docs/spike-report.md (the outcome), docs/assumptions.md (the evidence),
and the 2026-09-12 addenda in docs/session-log.md. The spike is COMPLETE and committed:
decision = build the agent (one-shot 57% vs 16.2% baseline; agency 38%, floor ~25%
without OCR; £0.034/case). Andy has signed off on the report — do not re-litigate it.

You are the orchestrator: delegate grunt work to subagents; keep judgement calls here.
Model calls go through the claude CLI in headless mode (see oneshot.py's call_model —
subscription auth, no API key; --tools "" whenever the payload must be the only input).
NTSB API key: NTSB_API_KEY env var via load_env_keys. Raw data never goes in git.

Goal: turn the spike's findings into a build brief Andy can size, then start only what
he green-lights.

1. Draft docs/build-brief.md. Ground every claim in the spike numbers. It must cover:
   - Scope framing (report §9): the agent replaces the analysis step, not the
     investigation; narrative-conditional pipeline (cheap path at 88% vs tool loop).
   - Tool #1: docket retrieval + born-digital PDF extraction (fixes 13/17 misses;
     scripts/b_docket_probe.py shows 9/14 dockets readable without OCR).
   - Live board: filter completionStatus == "Ongoing"; poll dockets and timestamp
     document arrivals prospectively (nothing temporal is recoverable after the fact —
     prelims are deleted at closure, dockets have no per-document dates).
   - Phase 2: OCR/vision for handwritten 6120 scans (buys agency 25% → 38%).
   - Eval plan: dev/test splits already defined; baseline.py and oneshot numbers are
     the bars to beat; state what "the agent wins" means numerically.
2. Run the owed phase_of_flight ablation before the brief is final: rerun the 40-case
   one-shot with phase_of_flight removed from evidence, diff top-1/top-3, and state
   what the defining-event coding smuggles in. Put the number in the brief.
3. List what the build repo needs that this spike repo does not have (it may be a new
   repo — recommend, don't decide).

STOP. Andy reviews the brief and decides: build here, new repo, or pause.
```
