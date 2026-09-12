# ntsb-spike

Pre-build validation for an NTSB probable-cause agent. **Nothing here is the agent.**

> **TL;DR** — The US National Transportation Safety Board publishes a determined *probable
> cause* for every aviation accident it investigates, coded into a fixed taxonomy. That is
> free, authoritative ground truth for a genuinely hard judgement task, which makes it
> unusually good material for a demonstration that can be checked rather than believed.
>
> Before building anything on it, this repository spent seven short sessions measuring
> whether the task actually needs an agent. **It does, narrowly.** One model call with no
> tools scores 57% where the naive baseline manages 16.2% — but that collapses to 12% on the
> half of recent cases with no written narrative, and in those cases the missing evidence is
> sitting in a public folder of documents that can simply be fetched. **Decision: build, with
> exactly one tool.**
>
> The agent is at [floyda/ntsb-probable-cause](https://github.com/floyda/ntsb-probable-cause).
> This repository is **complete and frozen** — kept intact so its numbers stay citable.

---

## What the NTSB publishes, and why it is unusual

The NTSB investigates every US civil aviation accident. When an investigation closes, the
public record contains both prose and a coded layer:

| | |
|---|---|
| **Factual narrative** | What the investigators found: the flight, the wreckage, the weather, the pilot's records |
| **Analysis** | The investigator's reasoning from those facts toward a conclusion |
| **Probable cause** | The determination itself, one or two sentences |
| **Occurrence code** | The category for *what happened*, from a taxonomy of about 58 |
| **Finding codes** | The categories for *why* — the contributing factors |
| **Docket** | A public folder of supporting documents: wreckage examination reports, records of conversation, the pilot's own accident form, photographs, sometimes video |

Everything is a work of the US federal government, so it is public domain: no licence
friction, no attribution requirement, and the docket needs no login.

**Where it comes from:**

- [NTSB Enterprise API developer portal](https://developer.ntsb.gov/) — the programmatic
  interface, `https://api.ntsb.gov/public`. This spike used `GetCasesByDateRangeV2`.
- [CAROL](https://data.ntsb.gov/carol-main-public/basic-search) — the public query and
  search tool, no authentication.
- [Bulk downloads](https://data.ntsb.gov/avdata) — the full dataset as a file. **Being
  retired on 5 April 2027** in favour of the API, which is why this project was built
  against the API from the start rather than migrating later.
- [A docket](https://data.ntsb.gov/Docket?ProjectID=104739) — one investigation's documents,
  to see the shape of the thing.

## Why this makes a good demonstration

A portfolio project is usually unfalsifiable: the system is asserted to work and the reader
takes your word for it. This dataset removes that problem, for five specific reasons.

1. **The labels already exist, and a federal agency wrote them.** Nobody on this project
   labels anything. That eliminates the failure mode where an evaluation turns out to be an
   argument with itself — which was what killed an earlier version of this project built on
   clinical trial data, where judging the answer needed domain expertise the author did not
   have.
2. **Part of the evaluation needs no judge at all.** Because the answer is a code from a
   fixed taxonomy, scoring is exact match: no model, no human, no rubric. Model judges are
   unreliable in ways this spike went on to measure directly — one agreed with a human only
   62.5% of the time.
3. **A stranger can check any output.** Every case has a public URL. A reader who doubts a
   result can open the same record and disagree specifically.
4. **It supports live, falsifiable prediction.** Investigations stay open for months — a
   median of 140 days to close. An agent can publish a timestamped prediction on an open
   case and be scored later by an external oracle that has no idea it exists.
5. **The volume is right.** Roughly 1,000–1,400 closed general-aviation cases a year:
   enough to sample properly, cheap enough to process exhaustively.

**The honest caveat**, which this spike measured rather than glossed: general-aviation
accidents are repetitive, so a trivial "always guess the most common cause" strategy scores
better than you would like. That baseline is reported alongside every result below,
because a number without its baseline means nothing.

## The answer

**Build it — but narrowly.** Three numbers decided it:

| | | from |
|---|---|---|
| One model call, no tools, on held-out cases | **57%** top-1 on the occurrence code | `oneshot.py`, n=40 |
| The dumbest sensible guess | **16.2%** top-1 | `baseline.py`, n=1,000 |
| Share of cases where fetching something changes the answer | **38%**, against a 20% bar | `decidability.py` |
| Measured cost per case | **£0.034**, against a £0.05 bar | `scripts/oneshot_summary.py` |

The model is genuinely reading the evidence — 3.5× the baseline — rather than exploiting a
common answer. But the 57% hides the finding that shaped the whole build:

| | one-shot top-1 | the model chose to abstain |
|---|---|---|
| Cases **with** a written factual narrative (n=24) | **88%** | 0 of 24 |
| Cases **without** one (n=16) | **12%** | 15 of 16 |

About half of 2020–23 cases have no factual narrative. So there is one axis of failure, and
it is not model skill — it is missing information. Of the 17 misses, categorised by hand:
**A:0, B:14, C:1, D:0**. A:0 means the model never misread evidence it was given. B:14 means
the fix was nearly always "go and read the rest of the file", and that file — the NTSB's
public docket — is fetchable.

**That is the entire case for an agent, and it is a measurement.** One tool, addressing 13
of 17 misses. Similar-case retrieval, regulation lookup and airframe history were designed
and then dropped: the labelled failures never asked for them.

## The test that produced it

Sample real cases. For each, ask: *can this be decided from the artifact alone?* Where it
cannot, classify what is missing.

| | missing information | implication |
|---|---|---|
| **A** | Semantic — two phrasings, can't tell if they agree | Prompting problem. **No agent.** |
| **B** | Elsewhere in the same record | **Fetching resolves it. Agent justified.** |
| **C** | Elsewhere entirely — another source | **Fetching resolves it. Agent justified.** |
| **D** | Not obtainable without physical evidence or an expert | Human queue. **No agent.** |

The number that matters is not the failure rate. It is **failure rate × (B+C share)** — the
share of all cases where going and looking changes the answer. Had A dominated, the honest
conclusion would have been to build a classifier and say so.

The threshold was written down *before* the measurement: 20% or more justifies an agent,
below 15% does not. It came out at 38%.

## What else it found

- **Leakage is real and measured, not waved away.** A blind human read of 30 factual
  accounts guessed the cause correctly **20%** of the time — at, not under, the acceptance
  bar. An automated scan of 4,241 accounts found a give-away phrase in 10.8%. So part of the
  88% is reading a well-curated account rather than raw investigation, and the report says
  so. `leakage.py`, `labelling/leakage.filled.csv`.
- **A model judge was not good enough to gate anything.** Asked to score the same 40
  answers a human had scored, it agreed **62.5%** of the time, and one-sidedly: it rejected
  14 of the 23 answers marked correct. That is why the build constrains output to codes
  scored by exact match. `scripts/ablation_phase_review.py`.
- **An ablation checked the evidence wasn't smuggling in the answer.** Removing
  `phase_of_flight` — which derives from the same coded record the answer comes from — cost
  at most about 2.5 points, all of it on cases that already state the phase in prose.
  `scripts/ablation_phase.py`.
- **The timeline of an investigation cannot be reconstructed afterwards.** The API deletes
  preliminary text when a case closes; docket listings carry no per-document dates. So the
  build has to record evidence arrival prospectively or never have it at all.
- **Dockets split by readability.** Of the 14 dockets behind the B-category misses, 9
  contain at least one born-digital document that extracts cleanly; 5 hold only a scanned
  handwritten form and photographs. That puts OCR in phase 2, and the decision does not
  depend on it. `scripts/b_docket_probe.py`.

## The data

29,383 case records via the NTSB Enterprise API — the platform that survives the April 2027
retirement of the downloadable datasets, so migration risk was resolved rather than
deferred. Filtered to 19,641 closed general-aviation cases from 2009 on. Splits: development
13,560 (to 2019), held-out 4,241 (2020–23), open 1,840 (2024+). A quarter of investigations
close within 82 days, half within 140, three quarters within 264. `fetch.py`, `volume.py`.

## Read in this order

1. [`docs/spike-report.md`](docs/spike-report.md) — the outcome and the deciding numbers. Two pages.
2. [`docs/build-brief.md`](docs/build-brief.md) — what to build, why, and what winning means in numbers. Ends with a glossary.
3. [`docs/session-log.md`](docs/session-log.md) — what surprised us. Surprises are the point of a spike.
4. [`docs/demo-criteria.md`](docs/demo-criteria.md) — the decidability test and the properties a demonstration has to have.
5. [`docs/design-notes.md`](docs/design-notes.md) — the original design this validated.
6. [`docs/assumptions.md`](docs/assumptions.md) — the register, with pass/fail per assumption.

## Layout

```
docs/               plan, design, criteria, assumptions register, session log, report
src/ntsb_spike/     one small script per spike task
labelling/          the hand-filled sheets every headline number rests on
scripts/            one-off probes (they hardcode paths — deliberately not reusable)
data/              raw and processed, never committed
```

`labelling/*.filled.csv` are the human labels behind the 57%, the 20% leakage figure and the
A/B/C/D breakdown. They are committed so every number in the report can be checked by
someone who did not produce it.

## Reproducing a number

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e .
cp config.example.yaml config.yaml    # then set NTSB_API_KEY in your environment
python -m ntsb_spike.fetch            # then any script from the table in docs/spike-report.md
```

The API subscription key is read from the `NTSB_API_KEY` environment variable and is not in
this repository.

## Rules this repo kept

- **Raw data is never committed.** Re-fetching is cheap; a stale copy in git is a liability.
- **The answer half is never passed to a model.** Analysis, probable cause and codes are
  assembled separately from evidence, in one function, with an assertion — not by convention.
- **Every number in the report is reproducible by one named script.** No numbers from memory.
- **Clinical tone.** These are fatal accidents. NTSB source text refers to people only by
  role, and no victim names appear anywhere in this repository.

## Licence

MIT — see [LICENSE](LICENSE). NTSB investigation data is a work of the US federal government
and is in the public domain.
