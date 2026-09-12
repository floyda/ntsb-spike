# NTSB probable-cause agent — build brief

*Drafted 2026-09-12 by the orchestrating agent from `docs/spike-report.md`,
`docs/assumptions.md` and the session log. Every number cites the script or
labelling sheet it came from. Sizing and the build/pause decision are Andy's.*

**How to read this.** Each section says what we would build, then *why the spike
data points that way*. Terms in **bold** on first use are explained in the glossary
at the end. Numbers in tables come from named scripts; if a number is a target or a
judgement rather than a measurement, it says so.

## 0. The whole brief in one paragraph

The spike said "build" ([report §2](spike-report.md)). A single model call with no tools
(the **one-shot**) picked the right **occurrence code** 57% of the time. The dumbest
sensible guess (the **conditional modal baseline**) manages 16.2%. So the model is
genuinely reading the evidence, not guessing. But the 57% hides a split: when a case has
a written **factual narrative**, the model scores 88%; when it does not, it scores 12%.
About half of recent cases (2020–23) have no narrative. In those cases the missing
information is almost always sitting in the **docket**, the NTSB's folder of supporting
documents. So the build is narrow: a tool that reads the docket, a pipeline that sends
easy cases down a cheap path and hard cases down the tool path, and a **live board** that
watches open cases as their evidence arrives. Cost is £0.034 per case, under the £0.05
limit.

## 1. Scope: what the agent does and does not do

**The agent replaces the analysis step, not the investigation** (report §9).

Why this framing matters: an NTSB investigation has two halves. Field investigators
gather evidence (wreckage examination, witness statements, maintenance records,
weather). Then an analyst reads that evidence and writes the verdict. The agent only
does the second half. It never sees the wreckage; it sees what the investigators wrote
down. This keeps the claim honest and matches what the data can support.

The verdict the agent produces has five parts:

| output | what it is | example |
|---|---|---|
| occurrence code | the NTSB's category for *what happened* | "Loss of engine power (total) — fuel starvation" |
| finding codes | the NTSB's categories for *why* (contributing factors) | "Pilot — fuel planning", "Environment — gusts" |
| probable cause | one or two plain sentences, as the NTSB writes them | "The pilot's inadequate fuel planning, which resulted in fuel exhaustion." |
| confidence | a number from 0 to 1 | 0.7 |
| abstain flag | "I do not have enough evidence to say" | true / false |

**The narrative-conditional pipeline.** "Narrative-conditional" just means: the route a
case takes depends on whether it has a factual narrative. This is the central design
decision, and it comes straight from Andy's labels on the 40-case one-shot
(`scripts/decidability_crosscheck.py`, `labelling/decidability.filled.csv`):

| cases | n | one-shot top-1 accuracy | model chose to abstain |
|---|---|---|---|
| factual narrative present | 24 | 88% | 0 of 24 |
| no factual narrative | 16 | 12% | 15 of 16 |

Reading this table: with a narrative, the model is almost as good as it gets from one
call, so those cases go down the cheap path (one call, no tools). Without a narrative,
the model nearly always says "not enough evidence", and it is right to. Those cases go
down the tool path. The decision of which path to take is a simple field check, not a
model decision. Note the model already abstains at exactly this boundary without being
told to, which is reassuring: it knows when it is guessing.

**Out of scope for version 1.** Andy's labels recorded, for each miss, what would have
fixed it. Nobody needed similar past accidents, regulations, or the aircraft's earlier
history, so none of those tools get built yet (report §6/§9). Reconstructing old
**preliminary reports** is also out: the API deletes them when a case closes (A8).

## 2. Tool #1: fetch the docket and extract born-digital PDFs

**Why this tool first.** Of the 17 misses in the 40-case run, Andy categorised what was
missing. The categories are A: the evidence was there and the model misread it; B:
something else in this case's file would have fixed it; C: something outside the case
(weather archive, precedent) would have fixed it; D: only physical evidence the NTSB had
could fix it. The result was A:0, B:14, C:1, D:0, with 2 left blank. A:0 means the model
never misread what it was given. B:14 means the fix is nearly always "go and read the
rest of the file". 13 of the 14 no-narrative misses were B. One tool addresses 13 of 17
misses.

**What "the docket" is.** For every case the NTSB publishes a web page listing the
supporting documents: records of conversation, wreckage examination reports, the
pilot's own accident report form (Form 6120), photographs, sometimes video. Some of these
PDFs were created on a computer ("born-digital"), so the text can be extracted directly.
Others are scans of paper, often handwritten, where the PDF is just a picture and the
text has to be recognised by **OCR**.

What the spike verified (A9, `scripts/a9_pdf_extract.py`, `scripts/b_docket_probe.py`):
- The docket page is `https://data.ntsb.gov/Docket?ProjectID={mKey}`. It is a plain
  HTML table, no login, no bot challenge. The API's `docketPage` field is empty on every
  record, so the URL has to be built from the case's `mKey`.
- Each document downloads from a `docBLOB` link found on that page.
- NTSB-authored born-digital PDFs extract cleanly with the `pypdf` library. Example: a
  wreckage-examination report yielded 5,631 characters of correct prose including the
  detail (a fuel-selector anomaly) that decided the case.
- Pilot-submitted scans are image-only and need OCR.
- Of the 14 dockets for the B misses: 9 contain at least one substantive born-digital
  document (8 if we are strict, since one hit is a garbled OCR layer); 5 are scan-only
  (small dockets with just a handwritten Form 6120 plus photos); none are empty. The
  median docket has 3 documents.
- Some dockets hold evidence no text tool can read (surveillance video packaged as an
  .exe). The NTSB usually writes a transcription memo, which substitutes.

**Build steps.** Fetch the page, parse the table, download the PDFs, classify each one
by characters of text per page (the probe used more than 300 as born-digital, fewer than
50 as scan), extract only the born-digital ones, and pass the text to the model as
evidence. Skip scans in version 1 and say so in the output.

## 3. The live board

**What it is.** A page that runs the agent on investigations that are still open,
records its prediction with a timestamp, and later scores that prediction against the
NTSB's published verdict. It is the "falsifiable in public" part of the demo.

**Which cases count as open.** Filter on `completionStatus == "Ongoing"`, not
"anything other than Completed". Why: 145 records look open but already carry a verdict.
They are all marked `N/A` because a foreign authority led the investigation
(`scripts/fresh_case_profile.py`). Genuinely Ongoing cases carry no findings, analysis
or cause, so the evidence/answer wall holds for live cases too.

**What a fresh case looks like** (same script, 6,812 open cases profiled by age):
- Day 1: aircraft, location, injuries, basic weather, and the coded event sequence
  including the **defining event**. This is filled in from day 1 on every case.
- First two weeks: preliminary narrative on 4% of cases, METAR (the coded airport
  weather report) on 17%, pilot flight hours on 0%, factual narrative on none. The
  preliminary narrative rises to about 40–43% over the following weeks.
- Time from accident to verdict: a quarter close within 82 days, half within 140, three
  quarters within 264 (`volume.py`). These are biased low because still-open cases are
  excluded. Expect verdicts to trickle in over months, not weeks.

**The constraint that shapes the design: nothing about timing can be recovered later.**
This was probed directly (report §9):
- The API deletes preliminary text when a case closes (A8: present on 822 Ongoing
  records, 17 N/A, 0 Completed).
- Docket listings carry dates for the docket as a whole, not per document.
- The web server's Last-Modified header reflects caching, not authorship.
- A PDF's internal creation date is a rough proxy and is absent on scans.

So if we want to know *when* each piece of evidence became available, the board has to
watch and record it itself: poll each open case's docket page, compare the document list
with last time, and stamp the time when something new appears. Every prediction is
stored as a new row with a fingerprint (hash) of the evidence it was made from. Nothing
is overwritten. A "resolution watcher" job notices when a case flips to Completed and
scores the standing prediction.

Example of why this matters: if the agent says "fuel starvation" on day 3 and "carburettor
icing" on day 40 after the engine report lands, we want to show both, with dates. Without
prospective recording, that story cannot be told.

Caveat carried from the design notes: in the first six months the board will have a
handful of resolved cases. That is an anecdote, not a statistic. The held-out numbers
(section 6) carry the weight; the board is the narrative device.

## 4. Phase 2: OCR or vision for the handwritten Form 6120 scans

**Why not now.** The 5 scan-only dockets from section 2 are unreadable without OCR.
Leaving them out cuts the reachable **agency** figure from 38% to about 25% (about 22.5%
if strict; session-log addendum 2026-09-12). That is still above the 20% line the spike
set for "an agent is justified", so the build decision does not depend on OCR.

**Why not never.** Those 5 dockets are a third of the docket-fixable cases. OCR is the
item that buys back that third.

**What we do not know.** The spike did not test OCR on handwriting. Two options exist:
send page images to a vision-capable model, or run conventional OCR software. Quality on
handwritten forms is unmeasured. Recommendation: size it as a small probe on the 5 known
dockets before committing to a build.

## 5. The phase-of-flight ablation (the number owed from Session 4)

**What the question was.** The evidence we give the model includes `phase_of_flight`
(takeoff, landing, en route, and so on). That value comes from the NTSB's coded
"defining event", which is the same record the answer's occurrence code comes from. So
there was a worry: are we handing the model part of the answer? Andy kept the field as
evidence in Session 4 because it is present from day 1 on live cases, with an
**ablation** owed to measure what it contributes.

**What the field hands over, structurally** (`scripts/ablation_phase.py`, held-out
cases 2020–23, n=4,241). The occurrence code is six digits: a 3-digit phase prefix and a
3-digit event suffix. Example: `552230` is phase `552` (a landing phase) plus event
`230`. Every prefix maps to exactly one phase value, so knowing the phase tells the model
which family of prefixes to look in. It does not tell it the event half: there are 39
prefixes and 76 suffixes, only 18.2% of phase values narrow to a single prefix, and
guessing the commonest code for each phase scores only 15.0% top-1 (`baseline.py`). The
hard part of the answer is the event suffix, which phase does not touch.

**The rerun.** Same 40 cases, same random seed, `phase_of_flight` removed from the
evidence (checked: no payload contained the key). All 40 calls succeeded.

| how it was scored | top-1 | top-3 | with narrative (n=24) | without (n=16) |
|---|---|---|---|---|
| original run, Andy's labels | 57.5% | 65.0% | 87.5% | 12.5% |
| ablated run, Haiku equivalence judge | 35.0% | 40.0% | 50.0% | 12.5% |
| ablated run, judge plus orchestrator re-read of the 9 flips | 55.0% | — | 83.3% | 12.5% |

**Why there are two ablated rows.** Nobody hand-labelled the rerun. Where the model's
answer text was identical to the original, Andy's label was reused. Where it changed, a
small model (Haiku) was asked "do these two verdicts mean the same thing?". That judge
turned out to be a poor stand-in for Andy: run on the original 40 answers it agreed with
him only 62.5% of the time, and its mistakes were one-sided. It rejected 14 of the 23
answers Andy had marked correct and accepted only 1 of his 17 wrong ones. So the 35% row
is a floor, not a measurement.

Reading the 9 cases the judge flipped from right to wrong
(`labelling/ablation.no_phase_of_flight.review.model.csv`,
`scripts/ablation_phase_review.py`): 8 give the same occurrence in different words, for
example "LOC-I" versus "LOC-I (Loss of Control - Inflight)", or "in-flight breakup"
versus "in-flight structural failure". One genuinely changed (WPR20LA126, loss of control
became loss of engine power). Across all 40 cases the wording changed on 31, but no case
went from wrong to right, and abstentions rose from 15 to 17.

**Conclusion.** Removing phase costs at most about 2.5 points of top-1 (57.5% to about
55%). All of the loss is on cases that have a narrative, which already states the phase
in prose. On cases without a narrative the score is 12.5% either way. So the 57% is not
resting on the defining-event coding. Both scored sheets have `.model.` in the filename
and are a model's opinion. The raw unlabelled rerun is in
`labelling/ablation.no_phase_of_flight.csv` if Andy wants ground truth instead.

**What this changes for the build.** Keep `phase_of_flight` as evidence (it is the one
day-1 signal on live cases). More importantly, the judge's 62.5% agreement is a concrete
example of the calibration trap the design notes warn about (§5), and it is the strongest
argument in this brief for **code-constrained output** (section 6): if the model returns
NTSB codes instead of free text, the headline score needs no judge at all.

## 6. Evaluation plan: how we will know the agent is better

**Data splits** are already defined in `config.yaml` and counted (`volume.py`):

| split | years | cases | rule |
|---|---|---|---|
| development | up to 2019 | 13,560 | use freely to build and tune |
| held-out | 2020–2023 | 4,241 | touch rarely; reported numbers come from here |
| open | 2024 onward | 1,840 | live board only; nobody looks at these |

Why three splits: if you tune on the cases you report on, the score means nothing. The
held-out set has been used once so far, for the 1,000-case baseline sample and the
40-case one-shot.

**Bars to beat**, all on the held-out split:

| metric | baseline (`baseline.py`, n=1,000) | one-shot ceiling (`oneshot.py`, n=40) |
|---|---|---|
| occurrence top-1 | 16.2% (commonest code given phase and weather) | 57% |
| occurrence top-3 | 32.2% | 65% |
| finding codes | precision 17.0% / recall 19.0% | not scored in the spike |
| no-narrative cases, top-1 | not computed | 12% (n=16) |
| cost per case | — | £0.034 measured (thinking tokens dominate) |

**"The agent wins" means, in numbers:**
1. Top-1 on the **no-narrative cases** rises from 12% toward the with-narrative 88%. The
   labels say 13 of 16 no-narrative cases were docket-fixable and 9 of 14 of those
   dockets are readable without OCR. Target for version 1 (a judgement, not a
   measurement): **at least 50% top-1 on no-narrative cases**. Below about 30% would
   mean the tool is not delivering the evidence the labels said was there.
2. Overall held-out top-1 above the **57%** one-shot ceiling. First on the same 40
   cases, so the comparison is like-for-like, then on a larger sample (300 cases costs
   about £10 at the measured rate).
3. **An ablation shows the tool earns its place.** Run the agent with and without the
   docket tool on the same cases. The drop should be concentrated in no-narrative cases.
4. **Abstention stays sensible.** On no-narrative cases the abstain rate should fall as
   the docket supplies evidence, while the agent still abstains on cases where only
   physical evidence could decide it.
5. **Cost stays under £0.05 per case** on average including tool calls, enforced by a
   hard cap in code.

**Three scoring layers** (from design-notes §5), and why the output format matters:
- Layer 1: occurrence code, top-1 and top-3. Layer 2: finding codes, precision and
  recall. Both can be scored by exact match with no model and no human, *but only if the
  model outputs NTSB codes*. In the spike it wrote free-text labels and Andy judged
  matches by hand. The build should give the model the list of codes with their
  meanings and require it to pick from the list. Then the regression check that gates
  every change runs automatically.
- Layer 3: the prose cause, scored by a model judge against the NTSB's sentence. This
  layer is checked against layers 1 and 2: where the judge says "match" but the codes
  disagree, the judge is wrong, and section 5 shows how easily that happens.

**Leakage guard** carries over unchanged: one function (`build_evidence()`) assembles
everything the model sees, with an assertion that no answer field is present. The 10.8%
of narratives containing a give-away phrase (`leakage.py`) is tracked as a statistic,
not filtered out.

## 7. What a build repo needs that this one does not have

The spike repo is a set of one-off measurement scripts around a config file and a data
file. It has no tests, no continuous integration, no agent package, and no storage. The
build needs:

- **An agent loop and tool interface.** The code that lets the model call tools (docket
  first, weather later using the Mesonet parameters verified in `config.yaml`), with a
  step budget, an abstain path, and a log of every step and its cost. Nothing like this
  exists here.
- **A docket client and PDF classifier/extractor** as an importable module with test
  fixtures. The probe scripts hard-code temporary paths and cannot be reused.
- **Code-constrained output** and a table of codes with their meanings
  (`decidability_form.build_code_lookups()` is the seed), so layers 1 and 2 score
  automatically.
- **An evaluation harness**: one command that runs a fixed list of cases, supports
  ablation flags, reports per slice (narrative / no narrative), gives confidence
  intervals and cost per run. `baseline.py` and `oneshot.py` are the numerical anchors
  but not a harness.
- **Storage**: a predictions table (case, evidence fingerprint, timestamp, answer, cost),
  docket document lists with first-seen timestamps, resolution outcomes. SQLite is
  enough at 1,000–1,400 cases a year.
- **A scheduler**: poll open cases and dockets, run the resolution watcher, lock
  predictions (the design notes suggest committing hashed rows to git so they are
  tamper-evident).
- **Model access via the API.** The spike ran through the `claude` command-line tool on a
  subscription. A scheduled service needs the Anthropic API and a key, which makes the
  £0.034 per case real money and makes the hard cap necessary.
- **Tests and CI**: the leakage assertion as a test, docket parser fixtures, a check
  that held-out cases never appear in development fixtures, and a retrieval-contamination
  test if similar-case search is ever added.
- **Data ingestion as a job**, not `fetch.py <start> <end>`: incremental updates by
  docket date and status, raw data kept out of git, the processed file rebuilt.
- **A public surface**: the live board page and a trajectory view showing the agent's
  steps and costs (demo-criteria §6), written in the clinical tone the design notes
  require (§9).

**Recommendation, not decision: a new repo.** The spike's value is its record: the
assumptions register, the report, the labelling sheets, and a script behind every number.
That record should stay frozen and citable. The build would replace most of the current
package and add tests, a scheduler and a user interface that the spike layout has no
place for. Carry over as-is: the field map in `config.yaml`, the evidence/answer roles,
`build_evidence()` and its assertion, the split definition, the two labelling sheets as
regression fixtures, and the 40 case IDs as the first like-for-like evaluation set.
Building in this repo is workable if Andy prefers one history; the cost is that spike
scripts and product code share a package and the "every number from a script" rule gets
harder to keep.

## 8. Sizing inputs (for Andy)

- Tool #1 is bounded by verified mechanics: two kinds of HTTP request, one HTML table
  parser, `pypdf`, a characters-per-page threshold. The unknowns are how much docket
  size varies (median 3 documents in the 14 probed) and rate limits (57 requests in the
  probe, no throttling seen).
- The live board's hard part is the poller and differ, not the page. It has to be
  running before there is anything to show, so it should start early.
- OCR is a separate probe on the 5 known scan-only dockets before any commitment.
- Evaluation cost at the measured rate (`scripts/oneshot_summary.py`, A7): 40-case
  like-for-like run about £1.34; 300 cases about £10; the full 3,000-case held-out set
  about £101. Runs on the subscription cost nothing extra but cannot be scheduled.

## Glossary

**Ablation.** Re-running an evaluation with one input or tool removed to measure what it
was contributing. If the score does not drop, that input was not earning its place.

**Agency (the 38% figure).** The share of all cases where going and fetching something
changes the answer. Computed as wrong-rate × share of misses in categories B or C. The
spike's rule: 20% or more justifies an agent; below 15% means build a classifier instead.

**Baseline.** The score of the dumbest sensible method. Every real result only means
something compared to this.

**Born-digital PDF.** A PDF created on a computer, so its text can be read directly.
Contrast with a scan, which is a picture of paper.

**Calibration (of a judge).** How often a model judge agrees with a trusted human on the
same items. A judge that agrees 62.5% of the time is not a substitute for the human.

**Code-constrained output.** Requiring the model to answer with a code from a fixed list
rather than free text, so answers can be scored by exact match.

**Conditional modal baseline.** "Guess the commonest answer, given something you know in
advance." Here: the commonest occurrence code for this phase of flight and weather.
Scores 16.2% top-1.

**Defining event.** The NTSB's coded choice of the single event that defines the accident,
from which both the occurrence code and the phase of flight are read.

**Docket.** The NTSB's public folder of supporting documents for one case.

**Evidence half / answer half.** Our split of each record. Evidence is what the agent may
see (factual narrative, aircraft, pilot, weather). Answer is what it must not see
(analysis, probable cause, codes). Enforced in one function with an assertion.

**Factual narrative.** The written account of the facts in the final report. Present on
82% of cases overall but only about 52% of 2020–23 cases.

**Finding codes.** The NTSB's categories for why the accident happened: the contributing
factors. A case usually has several.

**Held-out set.** Cases never used while building. Only scored at the end.

**Judge (LLM judge).** A model asked to score another model's answer against a reference.

**Leakage.** When the evidence gives away the answer, for example a "factual" sentence
that says the pilot failed to maintain airspeed. Measured at 20% in a blind human read.

**Live board.** The page that runs the agent on open cases, timestamps predictions, and
scores them when the NTSB publishes.

**Occurrence code.** The NTSB's category for what happened: a six-digit code, 3-digit
phase prefix plus 3-digit event suffix.

**OCR.** Optical character recognition: turning a picture of text into text.

**One-shot.** Sending the evidence to the model in a single message with no tools. Its
score is the ceiling for what you get without an agent.

**Phase of flight.** Where in the flight the defining event happened: taxi, takeoff,
climb, en route, approach, landing, and so on.

**Precision / recall.** For a set of predicted codes: precision is the share of predicted
codes that were right; recall is the share of the true codes that were found.

**Preliminary report.** A short early report the NTSB publishes weeks after an accident.
The API deletes it when the final report is published.

**Prospective recording.** Capturing events as they happen, because they cannot be
reconstructed afterwards.

**Stratified sample.** A sample drawn so that each category appears in proportion to how
common it is.

**Top-1 / top-3.** Top-1: the first guess is exactly right. Top-3: the right answer is in
the first three guesses.

**Trajectory.** The sequence of steps an agent took on one case: which tools it called,
what came back, what it decided, what it cost.
