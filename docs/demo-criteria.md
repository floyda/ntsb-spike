# What Makes a Good Demo — and How to Judge a Second Data Source

*Derived from the TrialWatch spike and the decidability labelling, September 2026.*

---

## Part 1 — What makes the demo good

Nine properties. TrialWatch has most of them already; any second data source should be judged on whether it keeps them.

### 1. Falsifiable
A stranger can take any output, follow it to the source, and check it. Most portfolio projects cannot be checked at all — you assert the system works and the reader takes your word. Being wrong in public and checkable is worth more than being unverifiable and impressive.

### 2. Measured, not asserted
Every claim has a number behind it and the method is visible. Not "the agent improves accuracy" but "38% of changes were undecidable from the diff alone, 95% CI 26–51%, n=60, one rater, here is the sheet." Confidence intervals rather than adjectives.

### 3. Negative results published
The strongest single signal available. "I built the loop and measured it against one-shot; it did not win, here is why" beats almost any success claim, because it proves the measurement was real rather than decorative.

### 4. Restraint demonstrated alongside capability
Choosing not to build something only reads as judgement if you could have built it. The spike is the evidence: the budget-allocation agent was designed, then killed by measurement, and the decision is documented. Restraint without evidence reads as inability.

### 5. Agency where it is warranted, nowhere else
Deterministic detection, deterministic routing, one narrow loop where the path genuinely cannot be hardcoded. The interviewer's first question is "why does this need an agent" — and the only answer that survives is a measurement.

### 6. The working is visible
A static page shows conclusions. A trajectory view shows the agent deciding, calling, reading, deciding again, with costs. This is the single most compelling artefact and the thing to walk someone through rather than describe.

### 7. Legible to a non-expert
A reader with no domain knowledge understands what changed and why it might matter, without leaving the page. This constrains the output schema — the model must produce a lay explanation — which in turn adds a grader. The presentation goal propagates backwards into the architecture, and saying so is itself a signal.

### 8. Cost instrumented and bounded
Hard caps in code, alarms, spend per unit of work published. "I instrumented my own cost ceiling" belongs in the README. Cost independent of traffic is a design property worth protecting.

### 9. Prior art acknowledged, not rebuilt
Name what already exists, say why you are not rebuilding it, and target the gap. TrialsTracker does deadline arithmetic; COMPare does manual outcome auditing; the unautomated gap is the judgement.

---

## Part 2 — The test for whether data supports agency

This is the hard-won part. The spike killed two agency arguments in succession, and the reason generalises.

**Agents earn their place when the information needed to decide is scattered and you do not know in advance where to look.** If the record in front of you already contains what you need, a single well-prompted call is better — cheaper, faster, more reliable, easier to evaluate.

### The decidability test

Sample 60 real cases. For each, ask: *can I decide this from the artifact alone?* When the answer is no, classify what is missing:

| | Missing information | Implication |
|---|---|---|
| **A** | Semantic — two phrasings, can't tell if they mean the same thing | Prompting problem. Better few-shot, better model. **No agent.** |
| **B** | Elsewhere in the same record — other versions, related fields, status | **Fetching resolves it. Agent justified.** |
| **C** | Elsewhere entirely — comparable cases, conventions, another source | **Fetching resolves it. Agent justified.** |
| **D** | Not obtainable — needs a document you don't have, or an expert | Human queue. **No agent.** |

**The number that matters is not the undecidable rate. It is `undecidable × (B+C)` — the share of all cases where going and looking changes the answer.**

TrialWatch scored 38% undecidable, of which 57% were B or C, giving 22%. Narrow but real. Had A dominated, the honest conclusion would have been to build a classifier.

### Four secondary tests

**Does the budget actually bind?** Scarcity only justifies allocation if the resource is scarce. TrialWatch costs ~$0.45/month to classify everything, so there is nothing to allocate and any triage heuristic trades recall for a rounding error. Check unit cost against realistic volume *before* building an allocation argument.

**Is the volume enough to be interesting but small enough to be affordable?** Too little and there is nothing to show; too much and the £20 ceiling binds in ways that distract from the engineering.

**Can ground truth be built by a non-expert?** This is the constraint that bit hardest. COMPare deliberately designed a test that students could apply. If labelling your gold set requires domain training you do not have, the project stalls at the gold set — and the gold set is what everything downstream depends on.

**Is the artifact self-contained by construction?** Structured registry fields are self-contained, which is precisely why they resist agency. Free text, cross-referenced records, and data split across sources are not — and that is where loops earn their keep.

---

## Part 3 — Judging a second public data source

### Non-negotiable

- **Public, no authentication, no scraping-hostile WAF.** Verify with a spike before committing.
- **Machine-readable and stable.** An undocumented internal endpoint is usable but must be named as the top risk, with the failure mode identified — silent re-wording produces wrong numbers rather than an outage, which is worse.
- **Ground truth constructible without domain expertise.**
- **Volume in the right band** — enough cases to sample, cheap enough to process exhaustively.
- **Legally and ethically clean to republish.** Check licences. Check whether the data is sanitised.

### What raises the agency score

- **Information split across records or sources**, so the model must decide where to look.
- **Free text rather than enumerated fields**, so semantic judgement is unavoidable — though watch that this pushes cases into category A, which does *not* help.
- **A reason to consult one source rather than another**, which is a genuine routing decision.
- **Variable evidence depth** — some cases settled in one lookup, others needing three, with no way to know in advance.

### The strongest structural pattern: cross-source disagreement

**When the same fact is recorded in two independent places, the interesting signal is where they disagree.** This is worth singling out because it satisfies almost every criterion at once:

- Information is scattered by construction, so agency is justified rather than argued.
- Ground truth is often mechanical — the two sources match or they do not.
- Findings are falsifiable, since a reader can open both records.
- The lay explanation writes itself: *these two official records say different things.*
- Depth varies genuinely, because reconciling a discrepancy may take one lookup or several.

Candidate shapes worth investigating, not recommendations:

- The same trial registered in two registries, with the outcome definitions compared.
- A registry record compared against the open-access publication — this is COMPare's actual comparison, closing the loop TrialWatch deliberately leaves open, feasible only for the open-access subset.
- Any regulatory filing that exists in parallel with a public database entry.

### Combining with TrialWatch specifically

Adding a second source is only worth it if it changes the *shape* of the problem, not just the volume. The question to ask: **does the second source turn category-A ambiguity into category-B or C?**

If a wording ambiguity in a registry record becomes decidable by consulting a second record, the second source has converted the unhelpful category into the helpful one — and that, rather than more data, is what justifies the loop.

If it merely adds more of the same kind of case, it costs build time and gold-set effort for no gain in the agency argument.

---

## Part 4 — The spike protocol, reusable

For any candidate source, before committing hours:

1. **Field availability** — is what you need actually populated, and how often is it missing?
2. **Access viability** — can it be fetched programmatically, at what rate, how brittle?
3. **Volume** — real counts over a real period, per unit of interest.
4. **Are the cases interesting?** — mechanically classify what changed. Distinguish signal from formatting artefact.
5. **Unit cost** — token count and money for one real case, extrapolated to monthly volume.
6. **Surprises** — data quirks a plan written from the outside would have missed.
7. **Decidability** — the A/B/C/D test above, on 60 proportionally sampled cases.

Steps 1–6 took roughly a session. Step 7 took about ninety minutes of labelling. Seven questions, four hours, and it killed two wrong architectures before either was built.

**That process is itself a portfolio artefact.** "I validated the premise before building on it, and here is the report" is a stronger opening than any amount of finished code.
