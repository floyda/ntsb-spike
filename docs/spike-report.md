# NTSB agent — spike report

*Drafted 2026-09-12 by the orchestrating agent from the assumptions register and
session log; every number cites its script or labelling sheet. Decision is Andy's.*

## 1. Question
Can the NTSB aviation investigation data support an agent that determines
probable cause from evidence, evaluated against the NTSB's own published verdicts?

## 2. Decision
**Build the agent.** The three numbers: one-shot model **57%** top-1 vs **16.2%**
conditional baseline (signal is real); wrong-rate × (B+C share) = **38%** — the
share of cases where going and fetching something changes the answer — against a
20% bar; cost **£0.034/case** measured, under the £0.05 line.
(Decision rule applied mechanically from spike-plan.md; all five build conditions
hold — A1–A3 pass, leakage 20% at the ≤20% bar, baseline beaten, agency ≥20%, cost under.)

## 3. What the data turned out to be
- **Access**: the official Enterprise API (`api.ntsb.gov`, GetCasesByDateRangeV2,
  subscription key) — the *post-2027-migration* platform, so migration risk is
  resolved, not deferred. One request fetched a month (132 cases, 13.4s); the full
  2009–2026 corpus is 29,383 records (`fetch.py`). Fallbacks verified: legacy CAROL
  API (no narratives) and avall.mdb (19 tables incl. narratives).
- **Completeness**: 100% of the 19,641 filtered closed GA cases have probable-cause
  text *and* occurrence codes (`fields.py`, A2). The factual account is a **separate
  JSON field** — no text-cutting (A3). Caveat: it is non-empty for only 82.3% overall
  and **~52% of 2020–2023** cases ("Basic (no factual)" report flavour).
- **Volume/time**: 1,000–1,400 closed GA cases/year; splits dev 13,560 / held-out
  4,241 / open 1,840. Time-to-close p25/median/p75 = 82/140/264 days (`volume.py`,
  survivorship-biased low) — a live board resolves in months, not weeks.
- **Live shape** (`scripts/fresh_case_profile.py`): a day-1 record is a skeleton —
  aircraft, location, injuries, *coded event sequence* — with almost no prose
  (prelim narrative 4% in the first two weeks, plateauing ~40%; pilot data 0%).
  Genuinely open (`Ongoing`) cases never carry findings/analysis/cause: the
  evidence/answer boundary holds live.

## 4. Baseline
From `baseline.py` on 1,000 stratified held-out cases (58-way occurrence taxonomy):

| baseline | top-1 | top-3 |
|---|---|---|
| unconditional modal | 6.7% | 12.1% |
| conditioned on phase | 15.0% | 30.1% |
| phase × weather | 16.2% | 32.2% |

Finding-code modal baseline: precision 17.0%, recall 19.0%. Class imbalance is mild —
the top 3 occurrence codes cover only 12.1% of cases, so nothing scores well by
freeloading on a fat head.

## 5. Leakage
Blind human read of 30 stratified factual accounts (labelling/leakage.filled.csv,
`leakage.py score`): cause guessed correctly **20%** — at, not under, the acceptance
bar; conclusion-style sentences flagged in 3% of accounts. Automated scan of 4,241
accounts: 10.8% contain a give-away phrase, dominated by the borderline "resulted in";
no structured evidence field acts as the verdict in disguise (purity scan).
`phase_of_flight` is the one judgement call: it derives from the NTSB's coded defining
event, kept as evidence (it exists from day 1 on live cases) with an ablation owed.
Reading: one-shot accuracy on narrative cases is partly reading a well-curated account,
not raw investigation — the 20% human floor says a fifth of accounts near-name the cause.

## 6. One-shot ceiling and decidability
40 stratified held-out cases, claude-sonnet-5, effort medium, no tools, evidence-only
payload (leakage assertion enforced; `oneshot.py`, scored in decidability.filled.csv
by `decidability.py`):

- **57% top-1 / 65% top-3** vs 16.2/32.2 baseline — ~3.5× lift.
- Split (`scripts/decidability_crosscheck.py`): **88% with a factual narrative,
  12% without**. The model abstained on 15/16 no-narrative cases and 0/24 others.
- Misses 17/40: **A:0, B:14, C:1, D:0** (2 blank). A=0 means the model never misread
  evidence it was given; the misses are missing-information, not misreading.
- Agency = 42% × 88% = **38%** (blank categories counted against B+C, so conservative).
- Tool priority: **docket retrieval** towers over everything (13/14 no-narrative
  misses are B); then weather (the one C case). Precedent/regulation never appeared.

## 7. Cost
Static estimate £0.0043/case typical, £0.0088 long (`cost.py`); **measured**
£0.0336/case mean on the real run (`scripts/oneshot_summary.py`) — thinking tokens,
not the evidence payload, dominate. Full 3,000-case held-out eval ≈ £101 measured,
×5 with ablations ≈ £504; both optional — the spike ran on a Claude subscription at
nil marginal cost via `claude -p`. Tools: historical METARs recover **byte-identical**
from the Iowa Mesonet archive (3/3, `scripts/a10_metar_probe.py`); docket PDFs split
by class — NTSB-authored born-digital documents extract cleanly with pypdf,
pilot-submitted scans need OCR (`scripts/a9_pdf_extract.py`). Probing all 14 B-case
dockets directly (`scripts/b_docket_probe.py`): **9/14 contain at least one substantive
born-digital document** (conservatively 8 — one hit is a garbled OCR layer); the other
5 are small CA-class dockets holding only a scanned handwritten Form 6120 plus photos —
unreadable without OCR.

## 8. Surprises
- Only ~52% of 2020–23 cases carry a factual narrative — and that absence, not model
  skill, is the single axis of failure (88% vs 12%).
- The API *deletes* preliminary text when a case closes (A8) — historical "day-10"
  replays are impossible; only a live feed captures the evidence timeline.
- The coded event sequence (incl. defining event) exists from **day 1** on open cases —
  investigator taxonomy arrives long before the verdict.
- Measured cost 8× the token-arithmetic estimate: reasoning tokens dominate.
- The model's abstention judgement was near-perfect (15/16 vs 0/24) without being
  asked to key on narrative presence.
- `docketPage` is null on all 29k records (URL must be built from `mKey`);
  `observationTimeUtc` is sometimes local time mislabelled UTC.
- The NTSB's own docket sometimes contains evidence no text pipeline reaches
  (surveillance video as a .exe player) — but the NTSB's transcription memo
  substitutes.

## 9. What I would build, and what I would not
**Build.** But scope it honestly: this agent does not replace the investigation —
field investigators gather the wreckage exams, witness statements and records; the
agent replaces (or previews) the *analysis* step, going from investigator-gathered
evidence to a verdict. On the live timeline that means: a thin day-1 estimate from
the skeleton record, then revisions as docket documents land over weeks — mirroring
exactly where the one-shot failed (no narrative → fetch the docket → 88%-grade
evidence becomes available).

First three things:
1. **Docket retrieval + born-digital PDF extraction** as tool #1 (it addresses 13 of
   17 misses); route by document type, skip scans initially.
2. **A narrative-conditional pipeline**: with-narrative cases are near-classifier
   territory (88% one-shot) — cheap path; no-narrative cases get the tool loop.
3. **A live board on `completionStatus == "Ongoing"`** (not ≠ Completed — foreign
   `N/A` cases carry verdicts), scoring the agent's standing answer against each
   NTSB verdict as it publishes (~median 140 days later).

On OCR: not tool #1, but not skippable either. Without it, 5 of the 14 B-case dockets
(the small scan-plus-photos CA-class ones) are unreadable, which cuts the reachable
agency from 38% to ~25% (conservatively ~22.5%) — still over the 20% line, so the
decision stands, but OCR of the handwritten Form 6120 is the phase-2 item that buys
back the last third. Would not build early: precedent search (zero demand in the miss
labels) and historical prelim reconstruction (the API destroys prelims — accept
live-only).

Owed before the build brief is final: the phase_of_flight ablation (what does the
NTSB's defining-event coding smuggle into the 57%?).
