# Session log

One entry per session. Keep it short. The point is that a reader (including
future you) can see what was actually done and what surprised you.

Template:

```
## Session N — <title> — <date> — <minutes spent>
Did:
Found:
Surprised by:
Changed my mind about:
Numbers produced (and which script):
Next:
```

---

## Session 0 — Access viability — 2026-09-11 — ~50 min (orchestrated: 4 subagents for research/download/probes; config, code and mapping done by the orchestrator)

Did:
- Located the authoritative migration notice on https://data.ntsb.gov/avdata (fetched raw, quoted verbatim): downloadable aviation datasets retire **2027-04-05**, replaced by the "Enterprise API platform"; the notice names **GetCasesByDateRangeV2** as the API to adopt. Its documentation is behind a sign-in wall at https://developer.ntsb.gov/ ("Please Sign In to view our content!") — not accessible without an account, so its request shape was NOT used or guessed.
- Instead used the *currently live* public CAROL API, with every detail taken from real saved responses (per CLAUDE.md rule 1's "or from a real response you have saved"): `POST https://data.ntsb.gov/carol-main-public/api/Query/Main` (paged summaries) and `POST .../Query/FileExport` (ZIP containing a 45-column CSV incl. ProbableCause/Findings). Request body structure (QueryGroups/QueryRules) verified against a real 200 response; probe artifacts in scratchpad, month fetch verbatim in `data/raw/fetched=2026-09-11/` (3 raw pages + export ZIP + 1:1 JSON of the CSV).
- Rewrote `fetch.py` for the observed contract (POST + ResultSetOffset paging + export); narrowed `common.load_raw_frame` to `cases_*.json`. Fetched 2022-03-01..31. Filled `config.yaml` api/fallback/filters/fields from observation.
- Ran `inspect_record.py WPR22LA118`: 45 fields, all structured scalars except `Findings` (long joined taxonomy string). No narrative text in the record.
- Docket: `https://data.ntsb.gov/Docket?ProjectID=104739` is server-rendered HTML with a parseable document table; `Docket/Document/docBLOB?ID=...&FileExtension=pdf&FileName=...` returned a valid PDF. No auth, no blocking, 2 requests.
- Downloaded `avall.zip` (fallback) and listed its 19 tables via mdbtools: Country, ct_iaids, ct_seqevt, dt_events, dt_Flight_Crew, eADMSPUB_DataDictionary, engines, events, Events_Sequence, Flight_Crew, flight_time, injury, NTSB_Admin, Occurrences, seq_of_events, states, aircraft, dt_aircraft, Findings, narratives.

Found (field mapping and why — for Andy to confirm):
- `id: NtsbNo` (the case number, e.g. WPR22LA118); `Mkey` is the numeric internal key used in Docket/Report URLs.
- `event_date: EventDate`; `status: ReportStatus` (observed values: "Completed" for finals, "N/A" for prelim-only) — closed predicate is `ReportStatus == "Completed"`; `MostRecentReportType` ("Final"/"Prelim") corroborates.
- `probable_cause_date: OriginalPublishedDate` — publication date of the report that carries the cause; nothing more specific exists in this record.
- GA filter: `FAR == "091"` (observed values: 091, 135, NUSC, NUSN, PUBU).
- Evidence (pre-accident descriptive facts, none states a conclusion): `Make`, `Model`, `N#` (registration), `EngineType`, `WeatherCondition` (VMC/IMC), `HighestInjuryLevel` (an outcome, not a cause — kept in evidence as the plan's field list does; Session 4 can move it), `DocketUrl`.
- Answer (verdict material): `ProbableCause` (the verdict sentence), `Findings` (the NTSB's coded why-taxonomy, " - "-joined string needing parsing).
- UNMAPPED (absent from the API record — do not guess): `factual_narrative`, `analysis_narrative` (exist only in the generated report PDF via `ReportUrl`, and in avall.mdb `narratives`); `phase_of_flight` and `occurrence_codes` (avall.mdb `Occurrences`/`Events_Sequence`); `pilot_certificate`, `pilot_total_hours`, `pilot_hours_in_type` (avall.mdb `Flight_Crew`/`flight_time`).

Surprised by:
- The API record contains NO narrative text at all — not even split badly. Factual account and analysis live only in the on-demand report PDF or the Access dump. A3/A2 (Session 1) must therefore be tested against avall.mdb narratives or PDF extraction, and the one-shot evidence pipeline may need the fallback file even if the API stays up.
- GetCasesByDateRangeV2 — the very endpoint the plan names — is undocumented publicly; the docs require a developer-portal account.
- Docket access is trivially easy (2 plain curls), while the "modern" API path is the gated one.
- No rate limiting anywhere; Cloudflare-fronted but no challenges.

Changed my mind about:
- fetch.py's assumed GET+page-param shape — the real API is POST with a filter-builder JSON body and offset paging; export is the richer source.
- Treating the API as the only Session 1 source — narratives force avall.mdb (or PDFs) into the main path, not just fallback.

Numbers produced (and which script):
- 132 aviation events for 2022-03, 4 HTTP requests, 12.9 s (`fetch.py`).
- Of the 29-row probe week: ReportStatus Completed 20 / N/A 9; FAR 091 18 of 29 (subagent probe, saved CSV).
- avall.zip 96,148,686 bytes; avall.mdb 558,522,368 bytes; 19 tables; `events` rows 31,124 (`mdb-tables`/`mdb-count`, commands in log above — not yet wrapped in a script).

Next:
- Andy: confirm the field mapping + unmapped list; decide whether Session 1 completeness runs against avall.mdb narratives (recommended) or PDF extraction; register a developer.ntsb.gov account to read the GetCasesByDateRangeV2 docs before 2027-04-05.

### Addendum (same day) — official API access obtained

Andy registered on the developer portal and supplied the OpenAPI spec (`public.yaml`)
plus a subscription key. Everything above about missing narratives applies only to the
legacy CAROL API and is superseded:

Did:
- Rewired `fetch.py`/`config.yaml` to `GET api.ntsb.gov/public/api/Common/v2/GetCasesByDateRange/`
  (auth: `Ocp-Apim-Subscription-Key` header; key only via the `NTSB_API_KEY` env var, never in the repo;
  marker pagination per the spec: `hasMore`/`nextMarker`, ≤1000 records/page).
- Refetched 2022-03: **132 records in 1 request, 13.4 s** — count matches the CAROL fetch
  exactly (132=132). CAROL raw kept as `data/raw/carol-legacy-fetched=2026-09-11/`.
- Re-ran `inspect_record.py WPR22LA118`: 66 top-level fields, deeply nested.

Found (revised mapping — see config.yaml for full paths):
- The V2 record is COMPLETE: `narratives[]` has separate `probableCause`,
  `analysisNarrative`, `concatenatedFactualNarrative`, `prelimNarrative` fields
  (strong early signal for A3 and A8); `aircrafts[].findings[]` are fully structured
  (findingCode, 4-tier taxonomy, modifier, `inProbableCause` flag);
  `aircrafts[].events[]` carry eventCode + `cicttPhaseSOEGroup` + `isDefiningEvent`;
  pilot certificates + a 16–24-row flight-time matrix; weather incl. raw METAR string.
- Previously-unmapped fields now mapped: factual/analysis narratives, pilot certificate
  and hours (via the flight-time matrix), occurrence codes (the events list).
- Still unmapped: `phase_of_flight` — it only exists as `cicttPhaseSOEGroup` *inside*
  the coded events list, i.e. entangled with the defining event (the answer-in-disguise
  column the plan predicted). Session 4 decides whether the defining event's phase can
  be extracted as evidence.
- Evidence/answer judgement calls to confirm: events[] → answer (they encode "what
  happened", the occurrence classification); findings[] → answer; the flight-time
  matrix, METAR, airframe hours, itinerary, airport/runway details → evidence.

Surprised by:
- `concatenatedFactualNarrative` is null on "Basic (no factual)" flavor cases
  (`factualFinalReportFlavor` field says so explicitly) — completeness rate is a
  Session 1 number to measure, and `investigationClass` may be a useful stratifier.
- Date semantics differ between the two APIs: WPR22LA118 is `eventDate` 2022-03-08
  (with `eventTimeUtc` 02:30) in V2 but 2022-03-07T19:30Z in CAROL — V2's date looks
  UTC-derived, CAROL's local. Explains a 1-week probe count mismatch (28 vs 29).
  Matters for month-boundary fetches.
- A9 bonus: the record embeds the raw METAR, so the Mesonet weather tool may only be
  needed for stations/times the record omits.

Numbers produced (and which script):
- 132 aviation events for 2022-03, 1 request, 13.4 s (`fetch.py` against the official API).

Next:
- Andy: confirm the revised mapping (esp. events[]→answer, matrix→evidence) before Session 1.
- Session 1 can now run entirely off the API record; avall.mdb demoted to true fallback.

---

## Session 4 (prep) — leakage sheet & scan — 2026-09-11 — ~45 min (orchestrated; flattening by python-senior-dev subagent)

Mapping confirmed by Andy (2026-09-11): events[]→answer, flight-time matrix &
METAR→evidence, injury level→evidence-for-now, phase_of_flight unmapped pending
this session's verdict.

Did:
- Fetched all of 2020–2023 via the V2 API: 48 monthly calls, 0 failures, 6,418 records
  (raw verbatim in data/raw/fetched=2026-09-11/). One hiccup: gpg-agent cache expiry
  broke `load_env_keys` in non-interactive shells until Andy unlocked it.
- Implemented nested-record flattening in common.py (config JSON-paths → real columns;
  derived.eventCodes defining-event-first; derived.findingCodes ordered by findingNumber;
  pilot hours extracted from the matrix; derived.far powers the Part 91 filter).
  config.yaml now points occurrence/finding codes and pilot hours at derived.* columns.
- Ran fields.py on the full set: n=4,241 after filters (post-2008, FAR 091, Completed).
- Generated labelling/leakage.csv (30 stratified cases, all with non-empty factual
  accounts, mean ~4,300 chars). leakage.KEY.csv written by the script and NOT opened.
- Ran leakage.py scan.

Found:
- Give-away phrase rate: 10.8% of 4,241 accounts contain ≥1 conclusory phrase
  ("resulted in" dominates at 278 hits; "improper(ly)" 54; "exceeded" 39). Under the
  20% kill line, pending Andy's blind read for the real A4 number.
- Structured-field purity scan: no field looks like the verdict in disguise —
  weather_condition and injury_level 0% single-code purity; engine_type 20% and
  pilot_certificate 46% are small-sample artifacts (rare values mapping to one code
  once), not systematic leaks. No recommendation to move any field to answer.
- Early Session-1 numbers (from fields.py, will be formalised then): A2 = 100%
  (probable cause + occurrence codes both present); factual narrative present in
  only 51.9% of filtered cases (the "Basic (no factual)" flavor); analysis and
  probable cause 100%; prelim_narrative and docketPage 0% filled in 2020–2023 data.

Surprised by:
- Half the closed GA cases have NO factual narrative in the record. The evidence half
  for those cases is structured fields only — the leakage sheet excludes them, and the
  one-shot design (Session 5/6) must decide how to handle them.
- 91/6,418 records have >1 aircraft (mid-air collisions etc.) — aircrafts[0] convention
  for now, revisit in Session 7 oddities.
- Parquet round-trips lists as numpy arrays; primary_code and the scan needed
  non-string-sequence handling (fixed in baseline.py / leakage.py).

Numbers produced (and which script):
- 6,418 records 2020–2023; 4,241 after filters (fields.py).
- Give-away rate 10.8%; per-phrase counts; purity table (leakage.py scan).

Next:
- Andy fills labelling/leakage.csv BLIND (guess cause + confidence, flag conclusory
  sentences), saves as leakage.filled.csv, runs `leakage.py score`. Then decides which
  fields (if any) move to answer, incl. the phase_of_flight question. Only after that:
  Session 3 baselines.

---

## Sessions 1 & 2 — completeness and volume — 2026-09-11 — ~40 min (run while Andy labelled; A12 by subagent)

Did:
- Back-filled 2009–2019 and 2024–2026-08 via the V2 API: 164 monthly calls, 0 failures
  (after fixing a zsh word-splitting bug that silently no-op'd the first attempt).
  Full raw set: 212 months, 29,383 records, 2009-01..2026-08.
- Rebuilt filtered.parquet: n=19,641 closed GA (FAR 091) post-2008 cases (fields.py).
- Ran volume.py; verified A12 via a subagent restricted to the factual-narrative column;
  produced labelling/leakage.model.csv via a blind subagent (model opinion, NOT ground
  truth — contents withheld from Andy until his sheet is exported).

Found (numbers from fields.py / volume.py):
- A2: 100.0% of filtered cases have probable cause AND event codes. Pass.
- A3: factual / analysis / probable cause are three separate JSON fields. Pass.
  Factual narrative present 82.3% overall but only ~52% in 2020–2023 — the "Basic
  (no factual)" report flavor is recent. Analysis + cause: 100%.
- Narrative length (non-empty skew): mean 553 tokens, median 296, p95 1,720, max 2,044.
- A8: prelimNarrative exists ONLY on open cases (822 Ongoing + 17 N/A of 29,383; zero
  Completed) — the API drops prelim text at final publication. Partial: live prelims
  yes, historical reconstruction would need archived avdata snapshots.
- A11: closed cases/year 1,100–1,400 (2009–2019), ~1,000–1,100 (2020–2023). Splits:
  dev 13,560 / held-out 4,241 / 2024+ 1,840. Time-to-close (last two event-years,
  closed only): p25 82d, median 140d, p75 264d — survivorship caveat, real tail longer.
- A12: no participant names in 20 read accounts; sweep of all 2,200 non-empty accounts
  found only a textbook-author citation. People are always "the pilot"/"the instructor".
- Class imbalance preview: top occurrence code 650470 with 2,048 of ~19.6k; top-15
  spread fairly flat — good sign for the baseline not being trivially dominant.

Surprised by:
- The factual-narrative fill rate FELL from ~95% (2009–2019 era, inferred from the
  82.3% overall vs 52% recent) — the NTSB moved to no-factual "Basic" finals for many
  recent GA cases. The held-out years are exactly the thin ones. May need to stratify
  evaluation by report flavor, or accept structured-fields-only evidence for half.
- Prelim text is destroyed (from the API's view) on closure — a live-prediction feature
  works going forward but can't be backtested historically without archives.
- 2020 volume dip (1,008) — COVID, presumably.

Numbers produced (and which script): all of the above from fields.py and volume.py.

Next:
- After Andy's leakage verdict: Session 3 baselines (conditioning only on surviving
  evidence fields). Session 5 later: docket text extraction quality (A9), METAR fetch
  (A10) — note METAR field only 24.3% filled overall, so the Mesonet tool matters.

---

## Session 4 — leakage verdict — 2026-09-11 — Andy ~1.5 h blind labelling + scoring

Did:
- Andy filled labelling/leakage.csv blind via the HTML form (leakage_form.py), then
  scored guesses against the key via the side-by-side form (leakage_compare.py);
  final sheet labelling/leakage.filled.csv with `correct` column; leakage.py score.

Found:
- A4 accuracy: 20% — a non-expert names the NTSB's cause from the account alone
  1 time in 5. Well under "right most of the time". PASS.
- A4 phrasing: Andy flagged conclusion-style sentences in 3% of the 30 accounts;
  automated regex scan says 10.8% corpus-wide (mostly "resulted in"). PASS (≤20%).
- Model-opinion sheet (leakage.model.csv, blind subagent, NOT ground truth):
  flagged conclusory wording in 17/30 accounts — far more liberal than Andy (1/30)
  or the regex; treat as an upper bound on stylistic leakage, not a contradiction.
- Purity scan (earlier): no structured evidence field maps values→single occurrence
  code systematically. Nothing moved to answer.

Surprised by:
- How low the human accuracy is (20%) given the accounts often contain rich physical
  evidence — reading is genuinely not investigating here. Good news for the project.

Numbers produced (and which script): 20% / 3% (leakage.py score); 10.8% (leakage.py scan).

Decision still open: phase_of_flight (see Session 0 addendum) — map from the defining
event's cicttPhaseSOEGroup as evidence, or leave unmapped. Session 3 baseline
conditioning depends on it.

RESOLVED same day: Andy chose to map it as evidence (`derived.phaseOfFlight`, the
defining event's cicttPhaseSOEGroup, fallback first event by sequence; 100% filled),
with a Session 6 ablation to measure what the NTSB's defining-event choice smuggles in.

---

## Session 3 — baselines — 2026-09-11 — ~10 min (scripted)

Did: rebuilt filtered.parquet with derived.phaseOfFlight; ran baseline.py on a
1,000-case stratified sample from the 2020–2023 held-out years.

Found (baseline.py):
- Unconditional modal occurrence-code baseline: top-1 6.7%, top-3 12.1%.
- Conditioned on phase of flight: 15.0 / 30.1. Phase × weather: 16.2 / 32.2.
- Class imbalance is mild: the top 3 occurrence codes cover only 12.1% of cases.
- Finding-code baseline (modal-occurrence's top-3 codes for everyone):
  precision 17.0%, recall 19.0%.
- A5: best conditional top-1 = 16.2% — far below the ~50% worry line. PASS.

Surprised by:
- How weak dumb guessing is here. The 58-way occurrence taxonomy is genuinely
  spread out; there is no fat head to freeload on. Any model beating ~16% top-1 /
  ~32% top-3 is adding real signal — a low bar in the best way.

Numbers produced (and which script): all of the above, baseline.py.

Next: Sessions 5 & 6 (cost, tools, one-shot ceiling, decidability). All three
kill-risk sessions (0, 4, 3) have now PASSED.

---

## Sessions 5 & 6 — cost, tools, one-shot ceiling — 2026-09-11 — ~45 min (orchestrated: 4 subagents; dry-run, eval run and docs by the orchestrator)

Did:
- No API key exists — Andy has a Claude subscription only. Verified (claude-code-guide
  subagent, against `claude --help` + docs) that the Claude Code CLI headless mode covers
  everything: `claude -p --model claude-sonnet-5 --effort medium --tools "" --system-prompt
  ... --output-format json --json-schema ...`, prompt on stdin, subscription auth.
  Rewired `oneshot.call_model()` to subprocess that command (python-senior-dev subagent;
  build_evidence untouched except numpy→list serialization; env scrubbed of
  ANTHROPIC_API_KEY/CLAUDECODE for the child). `--tools ""` is the leakage-critical flag:
  the model cannot read repo files, so build_evidence() stays the only input path.
- Ran cost.py (A7), the Iowa Mesonet METAR probe (A10, `scripts/a10_metar_probe.py`),
  docket PDF extraction on two dockets (A9, `scripts/a9_pdf_extract.py`).
- `oneshot.py --dry` leakage assertion passed; then the real 40-case stratified run:
  40/40 answered, 0 schema/CLI failures. `labelling/decidability.csv` written.

Found:
- A7 ✅ but with a lesson: static estimate £0.0043/case (cost.py, prompt+300 out tokens)
  vs measured £0.0336/case on the real run (`scripts/oneshot_summary.py`) — thinking
  tokens at effort=medium are ~8× the payload. Under the £0.05 line either way.
- A10 ✅: 3/3 stored METARs recovered byte-identical from the Mesonet archive (0-min gap).
- A9 ✅ split verdict: NTSB-authored born-digital PDFs extract perfectly with pypdf;
  pilot-submitted Form 6120s are scans (image-only) needing OCR — route by document class.
- Run health (oneshot_summary.py): abstention 15/40 (37.5%), confidence mean 0.49
  (min 0.05, max 0.90). No accuracy computed — that is Andy's labelling call.

Surprised by:
- The abstention rate: the model declined to name a cause on 15/40 held-out cases —
  and the cross-tab (oneshot_summary.py) is essentially perfect: 15 of the 16
  no-factual-narrative cases abstained, 0 of the 24 with a narrative did. Abstention
  IS narrative absence. The decidability question for those 15 is therefore pre-framed:
  B (docket would supply the missing facts) vs D (not obtainable) — and the one-shot
  accuracy story splits into "accuracy given a narrative" vs "coverage without one".
- Measured cost 8× the token-arithmetic estimate — reasoning tokens, not evidence
  payload, are the cost driver. cost.py's out_tokens=300 was the wrong mental model.
- `docketPage` null on all 19,641 records — docket URLs must be built from mKey.
- `observationTimeUtc` sometimes holds local time; METAR fetches must key on the
  ob's own ddhhmmZ group.

Changed my mind about:
- Needing an API key at all for the spike. The CLI's reported total_cost_usd doubles
  as the A7 measurement instrument.

Numbers produced (and which script): cost table (cost.py); METAR matches
(scripts/a10_metar_probe.py); extraction stats (scripts/a9_pdf_extract.py); run
health + measured cost (scripts/oneshot_summary.py).

Next: STOP — Andy fills occurrence_correct / top3_correct / category /
tool_that_would_fix_it in labelling/decidability.csv (save as decidability.filled.csv).
Then decidability.py + A6, and the Session 6 phase_of_flight ablation.

### Addendum (2026-09-12) — what a fresh case actually contains

Prompted by Andy's question mid-labelling: does a case arrive with the investigation
findings already in it? Fetched this month's cases (35 records, 2026-09-01..12) and
profiled all 6,812 open cases by age (`scripts/fresh_case_profile.py`):

- **The evidence/answer boundary holds live**: zero `Ongoing` cases carry findings,
  analysis or probableCause. (145 apparent exceptions are all `completionStatus: "N/A"`
  foreign-authority cases — a live pipeline must filter on == "Ongoing", not != "Completed".)
- **But `events[]` is 100% populated from day 1**, including the coded defining event
  (a 1-day-old case already had eventCode 300096 "Takeoff / Nose over/nose down",
  isDefiningEvent=true). Investigator-assigned what-happened taxonomy exists pre-closure —
  it also means phase_of_flight (from the defining event) is genuinely available to a
  live agent, which retroactively supports Andy's evidence call; the Session 6 ablation
  still measures what it smuggles in.
- **First two weeks are thin**: prelim narrative 4% (arrives weeks out, plateaus ~40-43%),
  METAR 17%, pilot flight-time matrix 0%, no factual narrative; solid skeleton only
  (aircraft, location, injuries, basic weather, event codes).
- Implication: a live "answer as evidence arrives" board is really a months-long
  trickle — day-0 output would rest on event codes + docket + external tools, with
  prelim text joining late. Numbers: scripts/fresh_case_profile.py.

### Addendum (2026-09-12) — decidability scored, A6 filled

Andy labelled the 40-case sheet (three form iterations along the way: evidence
payload embedded so A-vs-B/C/D is judgeable; NTSB codes decoded to labels; a real
autosave bug found and fixed — marks weren't persisting; plus list rendering).

Results (`decidability.py`, `scripts/decidability_crosscheck.py`):
- One-shot ceiling 57% top-1 / 65% top-3 vs baseline 16.2/32.2 — ~3.5× lift.
- Misses 17/40; A:0 B:14 C:1 D:0 (2 blank). Agency = 42% × 88% = **38%** → A6 PASS.
- The split IS the story: 88% accuracy with a factual narrative, 12% without.
  13/14 no-narrative misses labelled B. The agent's justification is almost entirely
  "fetch the docket when the record has no narrative" — plus the day-1 skeleton
  finding above, that is also exactly the live-case shape.
- A:0 is notable: when the evidence was in front of it, the model never misread it.

All assumptions now resolved: A1-A5, A7, A9-A12 pass; A6 pass; A8 partial (by design).
Next: STOP — Session 7 (apply the decision rule mechanically, draft spike report)
awaits Andy's go-ahead.

---

## Session 7 — decision and report — 2026-09-12 — ~20 min (orchestrator)

Did: applied the decision rule from spike-plan.md mechanically against the filled
register; drafted docs/spike-report.md from the template (every number cites its
script or sheet); filled the Decision block in assumptions.md.

Found: all five build conditions hold → **build the agent**. Deciding numbers:
57% vs 16.2% (one-shot vs conditional baseline), agency 38% vs 20% bar,
£0.034/case vs £0.05 bar. Leakage sits exactly AT the 20% bar — recorded as pass
per the rule's "20% or less", flagged in the report rather than softened.

Framing settled (Andy's question): the agent replaces the analysis step, not the
investigation — evidence is investigator-gathered; on live cases the agent gives a
day-1 estimate from the skeleton and revises as the docket fills.

Next: STOP — Andy reviews/edits the report; the decision is his. Open item carried
into any build brief: the phase_of_flight ablation.

### Addendum (2026-09-12) — OCR question: are B-case dockets readable without it?

Andy asked whether skipping OCR renders most dockets unreadable. Probed all 14
B-labelled miss dockets (`scripts/b_docket_probe.py`, 57 requests): 9/14 RICH
(≥1 substantive born-digital doc — records of conversation, memos, factual reports;
conservatively 8, one hit is a garbled OCR layer), 5/14 scan-only (all small CA-class
dockets: handwritten 6120 + photos), 0 empty. Median docket 3 docs.

Implication: without OCR the reachable agency is ~25% (conservatively ~22.5%) vs 38%
with it — still over the 20% build line, so the decision stands; OCR moves from
"would not build" to the phase-2 item. Report §7/§9 amended.
