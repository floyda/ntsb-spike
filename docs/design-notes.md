# NTSB Probable Cause Agent — Design Notes

*Working document. 10 September 2026. Alternative to the ClinicalTrials.gov brief.*

---

## 1. Why this dataset

### The problem it solves

The blocker on the clinical trials version was labelling. Materiality of a protocol amendment is a judgement call requiring domain expertise, so the gold set would have been *generated* by an unqualified labeller. Any eval built that way measures agreement with yourself.

**The principle this points to: find labels, don't make them.**

Three sources of free ground truth:
1. An authority already published the verdict.
2. Time revealed it — split by date, judge from what was knowable then.
3. It's a matching or reconciliation task a non-expert can verify.

NTSB is the cleanest example of the first. Federal investigators determine a probable cause for every closed investigation and publish it. **You are not the labeller.**

### The second problem it solves

The clinical trials design had one model call on a fixed path. That's defensible engineering but it isn't agency. Agency means variable step count, tool selection driven by what the last call returned, knowing when to stop, and recovering when a lookup comes back empty.

Accident investigation has that natural shape. Evidence is heterogeneous — narrative, weather, maintenance history, pilot certification, prior similar accidents — and which thread to pull depends on what you've found. Some cases resolve in two steps. Some don't resolve at all.

### Licence

Public domain, US government work. No attribution requirement, no scraping restriction, no licensing friction.

---

## 2. What the records contain

Each investigation produces a report with three free-text sections:

- **Factual information** — general information about the flight and the evidence.
- **Analysis** — the investigator's reasoning connecting facts to conclusion.
- **Probable cause and findings** — the determination, one or two sentences, averaging ~25 words.

Example of the last: *the pilot's loss of control while on approach, with a downdraft and lack of suitable terrain for an off-airport landing as contributing factors.*

### The coded layer — this is why NTSB wins

Alongside the prose there is structured coding across three levels:

| Level | Approx. categories |
|---|---|
| Phase | ~56 |
| Occurrence | ~58 |
| Subject | ~1,432 |

Phase of flight uses a broad taxonomy: takeoff, climb, cruise, descent, approach, landing, standing, taxi, manoeuvring, other. Weather is coded VMC or IMC.

**Categorical ground truth means part of the eval needs no judge at all.**

### Restriction

The coding system changed in 2008 and the pre-2008 scheme had real gaps — no code for controlled flight into terrain, among others. **Use post-2008 cases only.**

---

## 3. The leakage trap

The analysis section contains the investigator's reasoning toward the conclusion. If it reaches the agent's context, the agent isn't investigating — it's paraphrasing.

**Ingestion must split each record into an evidence half and an answer half, enforced in code with a test, not by convention.**

| Evidence half (agent sees) | Answer half (withheld) |
|---|---|
| Factual information | Analysis |
| Docket materials — witness statements, maintenance records, weather data, wreckage examination | Probable cause |
| | Coded findings |

### The subtler version

Factual reports for closed cases are sometimes written with the conclusion already known, so phrasing can hint. **Spot-check a sample by hand and report what you find.** An interviewer who has built evals will ask about leakage; having found it yourself is a far better answer than not having considered it.

### Retrieval contamination

`find_similar` must exclude the case under investigation and anything derived from it. Easy to get wrong. Needs a test.

---

## 4. The agent

Tools, not a fixed pipeline, so step count varies by case:

- **`get_factual(case_id)`** — sanitised factual narrative.
- **`get_docket(case_id)`** — supporting evidence.
- **`find_similar(query, filters)`** — prior accidents by aircraft type, phase of flight, conditions. **The load-bearing retrieval:** a human investigator asks "has this happened before to this type," and so should the agent.
- **`get_aircraft_history(registration)`** — prior events on the same airframe.
- **`get_pilot_context(case_id)`** — certification, hours, recency, as recorded.

A straightforward case resolves in two or three calls. A murky one — engine failure, no obvious cause — sends it after similar powerplant failures, maintenance history, fuel records.

**The agent must be able to abstain.** "Insufficient evidence" is a valid output and worth measuring separately.

### Required output

Structured, so it can be scored deterministically:
- An occurrence code from the NTSB taxonomy
- A set of subject/finding codes
- A prose probable cause
- A confidence value
- The evidence chain that supports it

---

## 5. Evaluation

Three layers. The deterministic ones anchor the judged one.

### Layer 1 — occurrence category
Exact match or top-3 accuracy against the NTSB code. No model in the loop. **This is the regression backbone that gates merges.**

### Layer 2 — finding codes
Set precision and recall over subject codes. Also deterministic. Catches the case where the agent gets the headline right but misses a contributing factor.

### Layer 3 — prose cause
LLM judge against the NTSB's stated cause, on a rubric:
- Same causal chain identified?
- Cause correctly separated from contributing factor?
- Any factor hallucinated that isn't in the evidence?

### The move that makes it defensible

**Validate layer 3 against layers 1 and 2.** Where the judge says "match" but the codes disagree, you have a judge calibration problem. Hand-check 50 of those and report judge agreement with the deterministic signal.

Most portfolio projects never get near this. It's the Shankar & Husain material applied to something real.

### Trajectory metrics

- Tool calls per case
- Whether it terminated sensibly
- Whether it abstained when evidence was thin

Abstention deserves its own number. A system that says "insufficient evidence" on genuinely ambiguous cases is more trustworthy than one that always answers.

---

## 6. Data splits

**Three sets, not two.**

| Set | Purpose | Discipline |
|---|---|---|
| Development | Iterate, tune prompts | Use freely |
| Held-out test | Reported numbers | Touch rarely |
| Open cases | Live blind predictions | Never seen by anyone |

Tuning against the cases you report on makes the numbers meaningless, and it's the first thing an experienced interviewer probes.

---

## 7. The live prediction board

Preliminary reports appear within days of an accident. Probable cause typically takes a year or more. So the agent can run on **open investigations** and publish timestamped predictions the NTSB will later adjudicate.

### The resolution watcher

A scheduled job that checks whether any open case with a stored prediction has closed, pulls the probable cause and codes, scores the prediction, and updates the public scoreboard.

**That is a production feedback loop with an external oracle** — a better thing to point at than a static eval run.

### Lock the predictions

Commit each with a timestamp and hash, ideally as a git commit so the history is public and tamper-evident. Without it, "my agent predicted this correctly" is unverifiable and a sceptical reader assumes the worst.

### Expect live numbers to be worse — and say so first

Simple cases close quickly. Cases still open are disproportionately the complex ones, so the open-case population is harder than the holdout and accuracy will drop.

**Predicting that in advance and then observing it is a stronger demonstration than a clean number.**

### Re-run rather than revise

Factual reports get amended as investigations progress. Evidence at day 5 differs from day 200. Store each run as a new versioned prediction rather than overwriting.

This gives a second thing to measure: **does confidence rise appropriately as evidence accumulates, or is the agent equally certain on day 5 with nothing to go on?**

### The honest limitation

NTSB investigates roughly 1,400 GA accidents a year, and probable cause takes a year or more. In the first six months the live board may have a handful of resolutions. **That is an anecdote, not a statistic.**

Frame it accordingly: **the holdout numbers carry the weight; the live board is the narrative device** showing the system runs unattended and is falsifiable. If the page implies the live board is the evidence, a reader who does the arithmetic will discount everything else on it.

---

## 8. Mechanics

| Item | Detail |
|---|---|
| Bulk data | `avall.zip` — all aviation investigation data 1962→present, MS Access, ~95MB, updated monthly |
| Search/export | Aviation Investigation Search — CSV and JSON downloads with hyperlinks to dockets and reports |
| Daily list | Aviation accidents sorted by date, updated daily |
| Query tool | CAROL — investigations, recommendations, dockets, all modes |

### Important

**NTSB is transitioning the downloadable dataset to an Enterprise API platform on 5 April 2027**, and already recommends `GetCasesByDateRangeV2` for bulk retrieval.

**Build against the API, not the MDB download**, or you'll be rewriting ingestion right as you start interviewing.

### Cost

95MB of Access DB is a one-off local job — extract to Parquet or SQLite and the whole corpus fits locally. No daily ingestion pipeline. Cost is model calls on batch runs plus a small scheduled watcher. Comfortably inside £20/month, likely well under.

---

## 9. Honest problems

**The prose cause is short.** ~25 words average. Easier for the judge, but a shallow answer can score well. The coded layers protect against this.

**GA accidents are repetitive.** A large fraction are fuel exhaustion, loss of control on landing, or continued VFR into IMC. **A trivial baseline that always guesses the modal cause will score better than you'd like. Report that baseline alongside your numbers** — it's honest and shows you know what a meaningful lift looks like.

**Retrieval contamination** — see §3.

**Tone.** These are fatalities. Keep the write-up clinical, avoid anything that reads as a game, keep victim names out of the output entirely.

**Not UK.** If UK relevance matters for applications, AAIB is the direct analogue under OGL v3 — but it's PDF bulletins rather than a query API, and far lower volume, so extraction overhead is significant at 2 hrs/week.

---

## 10. Where this sits against the alternatives

| Option | On-ramp | Retrieval argument | Ground truth | Region |
|---|---|---|---|---|
| **NTSB** | Moderate | Good | Excellent — coded + prose | US |
| UK planning + appeals | Easiest | Weakest | Excellent — decisions + inspector | UK |
| Patents (EPO OPS) | Hardest | Strongest — prior art is *the* hard retrieval problem | Good — examiner citations, oppositions | EU |
| Financial Ombudsman | Easy | Moderate | Good — upheld/not upheld | UK |
| Employment tribunals | Moderate | Moderate | Needs extraction | UK — **privacy concern, names real individuals; skip** |

---

## 11. Open items

- [ ] Decide NTSB vs UK planning vs patents.
- [ ] If NTSB: build ingestion against `GetCasesByDateRangeV2`, not the MDB.
- [ ] Write the layer-3 rubric.
- [ ] Design and test the evidence/answer split.
- [ ] Establish the modal-cause baseline before building anything clever.
