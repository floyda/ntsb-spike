# Assumptions register

Fill in as sessions complete. "Evidence" means the number or file that proves it —
not a feeling. Every row should be reproducible from a script or a labelling sheet.

| # | Assumption | Session | Status | Evidence | Date |
|---|---|---|---|---|---|
| A1 | Closed cases retrievable via the V2 API, not only the Access dump | 0 | ✅ pass | 132 cases for 2022-03 in ONE request/13.4s via the official Enterprise API: `GET api.ntsb.gov/public/api/Common/v2/GetCasesByDateRange/?startDate&endDate&mode=aviation` with `Ocp-Apim-Subscription-Key` header (Andy's portal account; spec in `public.yaml`). Marker-paginated, ≤1000 records/page. Records are complete: narratives (factual/analysis/probable cause/prelim), coded findings, event sequence, pilot, weather incl. METAR. Raw verbatim in `data/raw/fetched=2026-09-11/` (`fetch.py`). Count cross-checks CAROL legacy API (132=132). This is the post-2027-migration platform — migration risk resolved. Earlier same-day partial (CAROL-only, V2 docs gated) superseded once Andy supplied portal access. | 2026-09-11 |
| A2 | Post-2008 cases carry probable cause **and** codes ≥80% of the time | 1 | ✅ pass | 100.0% of 19,641 filtered closed GA cases 2009–2026 have both probableCause text and event codes (`fields.py`). | 2026-09-11 |
| A3 | Factual account is a separate field from analysis/probable cause | 1 | ✅ pass | V2 record stores narratives[].concatenatedFactualNarrative, .analysisNarrative and .probableCause as three separate JSON fields — no text-cutting needed. Caveat: factual field non-empty in 82.3% overall but only ~52% for 2020–2023 ("Basic (no factual)" report flavor); analysis+cause 100% (`fields.py`). | 2026-09-11 |
| A4 | Factual accounts don't leak the conclusion (≤20%) | 4 | ✅ pass | Andy's blind read of 30 stratified accounts (labelling/leakage.filled.csv, scored via leakage.py score): cause named correctly 20% of the time; conclusion-style sentences flagged in 3% of accounts. Automated scan across 4,241 accounts: 10.8% contain a give-away phrase (dominated by borderline "resulted in"). Purity scan found no structured evidence field acting as the verdict in disguise. | 2026-09-11 |
| A5 | Conditional modal baseline leaves room for lift (<~50% top-1) | 3 | ✅ pass | On a 1,000-case stratified sample from 2020–2023 (baseline.py): unconditional modal top-1 6.7% / top-3 12.1%; conditioned on phase 15.0/30.1; phase×weather 16.2/32.2. Class imbalance mild: top-3 occurrence codes = 12.1% of cases. Finding-code baseline: precision 17.0%, recall 19.0%. Best conditional top-1 16.2% — far below the 50% worry line. | 2026-09-11 |
| A6 | Wrong-rate × (B+C share) ≥ 20% | 6 | ☐ untested | | |
| A7 | Unit cost < £0.05 per case | 5 | ☐ untested | | |
| A8 | Preliminary reports recoverable for historical cases | 1 | ⚠️ partial | prelimNarrative is populated only while a case is open: 839/29,383 records have it (822 Ongoing, 17 N/A, 0 Completed) — the API drops prelim text when the final publishes. So live prelims: yes; historical prelims for closed cases: not via the API. Untested mitigation: archived monthly avdata snapshots / Wayback. Per plan: drop or descope the "answer as evidence arrives" feature for historical cases. | 2026-09-11 |
| A9 | Docket documents accessible and extractable | 0 | ⚠️ partial | Accessible: yes. `https://data.ntsb.gov/Docket?ProjectID=104739` (case WPR22LA118) returns a server-rendered HTML table of documents (2 docs, titles+IDs+types parseable); `Docket/Document/docBLOB?ID=13431351&FileExtension=pdf&FileName=...` returned a valid 2,232,590-byte PDF (`%PDF-1.6`). Plain curl, no auth, no Cloudflare challenge, 2 requests. Extractable (text quality): untested — Session 5. | 2026-09-11 |
| A10 | Historical METARs fetchable for station/time in the account | 5 | ☐ untested | | |
| A11 | Volume and time-to-close support the splits and a live board | 2 | ✅ pass | Closed GA cases/year: 1,100–1,400 (2009–2019), 1,000–1,100 (2020–2023) (`volume.py`). Splits: dev 13,560 / held-out 4,241 (≥3,000 ✓) / 2024+ 1,840. Time-to-close for cases closed from the last two event-years: p25 82d, median 140d, p75 264d — caveat: survivorship (still-open cases excluded), so true medians are longer; live board should expect months, not weeks. | 2026-09-11 |
| A12 | No personal names in accounts; data free to republish | 1 | ✅ pass | 20 accounts read in full (seed=7): 0/20 name accident participants — people are always "the pilot"/"the instructor"/"a witness" etc. Automated sweep of all 2,200 non-empty accounts: honorific pattern hit once (a textbook-author citation, WPR20LA194); First-Last bigram hits all false positives (airports/places/companies). Script: scratchpad a12_names_check.py; subagent-run 2026-09-11. No copyright/licence markers seen in narrative text (text-level observation, not legal advice). | 2026-09-11 |

Status values: ☐ untested · ✅ pass · ❌ fail · ⚠️ partial (explain in Evidence)

## Fields moved from evidence to answer in Session 4

| Field | Why |
|---|---|
| | |

## Decision

Applied the rule in `spike-plan.md` on: ____

Outcome: ☐ build the agent · ☐ build the classifier version · ☐ stop · ☐ grey zone (explain)

Reasoning:
