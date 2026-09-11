# NTSB Probable-Cause Agent — Spike Plan

*Purpose: before writing any agent code, check every assumption the project depends on. If one of them is wrong, better to find out in a few hours than after forty. Target: about 8 hours spread over 3–4 weeks. Three of the sessions (0, 4 and 3, in that order) can kill the project on their own, so do those first — they take about 3 hours.*

---

## Words used in this document

Read this once; the rest of the plan uses these terms without re-explaining them.

**Case.** One NTSB investigation of one accident. Each closed case has a written account of the facts, the investigators' analysis, a one-or-two-sentence "probable cause", and a set of codes.

**Occurrence code.** The NTSB's category for *what happened* — e.g. "loss of engine power", "loss of control on landing". Every closed case has one (sometimes more). About 58 categories exist.

**Finding codes.** The NTSB's categories for *why* — the contributing factors, e.g. "pilot: use of carburettor heat", "environment: gusts". A case usually has several.

**Evidence half / answer half.** Our split of each case. The evidence half is what the agent is allowed to see (the factual account, the aircraft and pilot details). The answer half is what it must not see (the analysis, the probable cause, the codes). The agent's job is to get from the first to the second.

**Leakage.** When something in the evidence half gives away the answer — for example a "factual" sentence that says "the pilot failed to maintain airspeed". If the evidence leaks, the agent isn't investigating, it's reading, and any accuracy number is inflated.

**Baseline.** The score you would get with the dumbest possible method. Every real result is only meaningful compared to this.

**Modal.** "The most common one." The modal occurrence code is whichever code appears most often across all cases. A *modal baseline* means: guess the most common answer every single time, and see how often that's right.

**Conditional modal.** Same idea, but split by something you know in advance. "Given the accident happened during landing, guess the most common cause *for landing accidents*." This is a smarter dumb method and a fairer baseline.

**Top-1 / top-3 accuracy.** Top-1: how often the first guess is exactly right. Top-3: how often the right answer is somewhere in the first three guesses.

**Precision / recall (for finding codes).** The agent outputs a set of codes; the NTSB has its own set. Precision = of the codes the agent gave, what fraction were correct. Recall = of the codes the NTSB gave, what fraction did the agent find. High precision, low recall means it's cautious and misses things; the reverse means it over-lists.

**Held-out set.** Cases you deliberately never look at while building. You only score on them at the end. If you tune the agent on the same cases you report on, the numbers mean nothing.

**Split.** Dividing the cases into groups by date: a *development* set to build with, a *held-out* set to report on, and *open* cases (not yet decided by the NTSB) for live predictions.

**One-shot.** Sending the model the evidence in a single message and asking for the answer, with no tools and no looking anything up. This is the "just a classifier" version. Its score is the ceiling for what you could get *without* an agent.

**Tool.** A function the model can call to fetch something — get the weather, look up similar past cases. An agent is a model that decides which tools to call and in what order.

**Ablation.** Re-running the evaluation with one tool switched off, to measure how much that tool was contributing. If accuracy doesn't drop, the tool wasn't earning its place.

**Tokens.** The units a model reads and writes; roughly three-quarters of a word each. Cost is per token, so the length of the evidence matters.

**Unit cost.** Money spent to process one case.

**Stratified sample.** A random sample chosen so that each category is represented in proportion — so you don't accidentally pick 30 landing accidents and no engine failures.

**Percentiles (p25, median, p75).** For a list of numbers sorted smallest to largest: p25 is the value a quarter of the way up, the median is halfway, p75 is three-quarters. Together they describe the spread better than an average.

**Class imbalance.** When a few categories account for most of the cases. Matters because guessing those categories scores well without any skill.

**Decidability categories (A/B/C/D).** Our test for whether an agent is needed. For a case the one-shot model got wrong, ask what was missing:
- **A** — nothing was missing; the answer was in the evidence and the model misread it. Fix with better prompting. No agent needed.
- **B** — the answer needed other parts of the *same case* the model wasn't shown (a docket document, the aircraft's history). Fetching it would fix it. Agent justified.
- **C** — the answer needed something *outside the case*: similar past accidents, a weather report, a regulation. Fetching it would fix it. Agent justified.
- **D** — not obtainable; the NTSB had physical evidence you don't have. Nothing fixes it. The agent should say "insufficient evidence".

The number that matters is: (share of cases the one-shot got wrong) × (share of those that are B or C). That's the fraction of all cases where *going and looking* changes the answer. If it's small, build a classifier and be honest. If it's meaningful, the agent earns its place.

**Docket.** The NTSB's folder of supporting documents for a case — witness statements, engine examination reports, weather studies. Mostly PDFs.

**METAR.** A standard aviation weather report from an airport station at a given time.

---

## 0. The assumptions this spike exists to test

| # | Assumption | Tested in | Kill threshold |
|---|---|---|---|
| A1 | Closed cases can be downloaded through the NTSB's web API, not only the big database file | Session 0 | No working API → use the database file, and record that the April 2027 API migration is the top risk |
| A2 | Post-2008 cases have both a probable cause and the codes, nearly always | Session 1 | Fewer than 80% of closed cases have both |
| A3 | The factual account is stored separately from the analysis and probable cause, not mixed into one block of text | Session 1 | Mixed → we'd have to cut the text apart ourselves, which is fragile and costly |
| A4 | Factual accounts don't give away the conclusion in how they're worded | Session 4 | More than 20% of accounts read like a verdict → the evaluation is compromised |
| A5 | Guessing the most common cause isn't already very accurate, so there's room for the agent to do better | Session 3 | If "guess the most common cause for this phase of flight" is right more than half the time, the agent has to be far better than that to be interesting |
| A6 | A meaningful share of the cases the one-shot model gets wrong are fixable by looking something up (categories B and C), rather than being misreads (A) or unobtainable (D) | Session 6 | Wrong-rate × (B+C share) below 15% → it's a classifier, not an agent |
| A7 | Processing one case costs almost nothing | Session 5 | Over £0.10 per case with full evidence → we'd have to sample, and ablations get expensive |
| A8 | The NTSB's *preliminary* report (published weeks after an accident, before the final one) can still be retrieved for old cases | Session 1 | Not retrievable → drop the "how does the answer change as evidence arrives" feature |
| A9 | Docket documents can be downloaded and their text extracted | Session 0 | Not accessible → the first version of the agent runs without the docket; say so |
| A10 | Historical weather reports can be fetched for the station and time named in the account | Session 5 | Not fetchable → weather comes only from what the account says |
| A11 | There are enough cases per year, and cases close fast enough, to support the splits and a live scoreboard | Session 2 | Informational — sets expectations, doesn't kill |
| A12 | Accounts don't contain people's names, and the data is free to republish | Session 1 | Names present → remove them at import time and add a test that checks |

---

## Session 0 — Can we get the data? (30–45 min) — CRITICAL PATH

Goal: one real month of closed general-aviation cases saved on disk, fetched through the API.

- Find the current documentation for the NTSB's CAROL system and the `GetCasesByDateRangeV2` call. Write down: does it need a login or key (expect no), how many requests per minute are allowed, how results are paged, what format they come in, and the stated date and details of the 2027 migration.
- Fetch one month of cases (for example one month in 2022). Save the raw response, in a folder named by date. Note how many requests it took and how long.
- Open one case and read it end to end. List every field it contains. Mark each as "structured" (a code, a number, a category) or "free text".
- Try to open the public docket for that same case. Is there a way to list its documents programmatically? Are they PDFs? Does the site block automated access?
- In the background, download the full database file (`avall.zip`) as the fallback. Note its size and what tables it has.

Write down: API works yes/no; list of fields; docket access yes/no; migration date and what it changes.

---

## Session 1 — What's actually filled in? (1–1.5 h)

Goal: real percentages for which fields are populated, not guesses.

Using the month from Session 0 (widen to three months if it's quick):

- Keep only: accidents after 2008, general aviation (US "Part 91" flying), status closed.
- For each case, record whether each of these is present: factual account; analysis text; probable-cause text; occurrence code; phase-of-flight code; finding codes; aircraft make, model and registration; engine type; pilot certificate and hours; weather condition (visual or instrument); injury level.
- Measure how long the factual accounts are, in tokens. This feeds the cost estimate later.
- Check A3: is the factual account its own field, separate from analysis and probable cause? Or is it one long text with headings? If headings, check whether they are consistent enough that a simple rule could split them reliably.
- Check A8: does the record include the preliminary report text or any earlier versions? If not, spend no more than 15 minutes checking whether old monthly copies of the database file exist anywhere (for example on the Internet Archive) that would let you reconstruct preliminaries for some cases. This is nice-to-have, not essential.
- Check A12: read 20 accounts looking for personal names. Note whether the pilot is only ever called "the pilot".

Write down: a table of field → % present; account length statistics; the answers to A3 and A8.

---

## Session 2 — How much data, and how fast does it arrive? (45 min)

Goal: real counts that decide how to split the data and what to expect from a live scoreboard.

- Count closed general-aviation cases per year from 2009 to now. Expect roughly 1,200–1,500 a year; confirm.
- Count cases that are currently open and have a preliminary report.
- For cases closed in the last two years, measure the gap between the accident date and the probable-cause date. Report p25, median and p75. **This number answers your long-standing worry about slow turnaround. Write it down and design the web page around it.**
- Count how many cases fall under each occurrence code and each phase of flight. You'll need these for the baseline anyway.
- Propose the split: build with cases up to 2019; report on 2020–2023; keep 2024 onwards as open cases for live predictions. Check the 2020–2023 group has at least 3,000 cases.

Write down: cases per year; time-to-close percentiles; a realistic count of how many open cases will be decided within six months (it will be small — that's fine, just be honest about it).

---

## Session 3 — How well does dumb guessing do? (1 h) — CRITICAL PATH

Goal: the number every later result gets compared to.

Take a random 1,000 closed cases from the 2020–2023 years.

- Simple modal baseline: guess the single most common occurrence code for every case. What share are right (top-1)? What share are in the three most common codes (top-3)?
- Conditional modal baseline: for each case, guess the most common occurrence code *for that phase of flight*. Then do it again using phase of flight *and* visual-vs-instrument weather. Report top-1 and top-3. Only condition on structured fields that Session 4 kept in the evidence half — if a field was withheld as answer-in-disguise, the agent won't see it, so the baseline mustn't use it either.
- Finding-code baseline: for the guessed occurrence, output the finding codes that most often go with it. Measure precision and recall against the real finding codes.
- Note the class imbalance: what share of cases are the top three occurrence codes put together?

Write down: a table of baseline scores. If the conditional top-1 is above about 50%, note that the agent must beat that clearly to be interesting, and that the interesting cases are the uncommon ones. Plan from the start to report accuracy on the uncommon cases separately.

---

## Session 4 — Does the evidence give away the answer? (1 h) — CRITICAL PATH

Goal: know whether the evidence half secretly contains the verdict.

- Pick 30 factual accounts (not analysis, not probable cause) from the 2020–2023 years, stratified across occurrence codes.
- For each: cover the probable cause. Read the account. Write one line saying what you think caused the accident and how sure you are. Then uncover and compare.
- Separately, underline any sentence that states or strongly implies a conclusion rather than a fact — words like "failed to", "inadequate", "improperly", "did not maintain".
- Compute two things: how often you got the cause right from the account alone, and what share of accounts contain conclusion-style sentences.
- Also check the structured fields: is there a column (a "defining event" or similar) that is really the answer in disguise? It would need to be withheld from the agent.

Write down: the leakage rate; a list of the give-away phrases (these become either an automatic cleaning rule or a stated limitation); any structured fields to withhold.

How to read the result: some leakage is normal and can be reported. The project dies if you — a non-expert — can name the cause from the "facts" most of the time. That would mean the task is reading, not investigating, and the accuracy numbers would be hollow.

---

## Session 5 — What does one case cost, and do the tools work? (1 h)

Goal: cost per case, and a yes/no on the two external tools.

- Build the full evidence half for one typical case and one long case: account plus structured fields plus (if you have it) the docket document list. Count tokens.
- Send each to a small, cheap model in a single message: "Given this evidence, give the occurrence code, the finding codes, a one-sentence probable cause, and a confidence from 0 to 1." Record tokens in, tokens out, and cost. Multiply out to 3,000 cases × (one full run plus each planned ablation).
- A10: find the weather station and time mentioned in the account. Try to fetch that METAR from the Iowa Mesonet ASOS archive (a free historical weather source). Does it work? Any rate limit?
- A9: download one docket PDF (an engine examination or a weather study). Extract the text. How clean is it? How long?

Write down: tokens and cost per case (typical and long); estimated cost of a full evaluation with ablations; weather tool works yes/no; docket extraction quality.

---

## Session 6 — Is an agent actually needed? (1.5 h)

Goal: the decisive test. This session says "agent" or "classifier".

- Take 40 cases from 2020–2023, stratified. Run the single-message version from Session 5 on each. Score the occurrence code (exact and top-3) and the finding codes (precision and recall) against the NTSB's codes. This is the *no-tools* score — the best a plain classifier could do.
- For every case it got wrong (and a few it got right but with low confidence), decide which category the miss falls in:
  - **A** — the answer was in the evidence; the model misread it.
  - **B** — the answer needed other material from the same case that the model wasn't given: a docket document, the aircraft's earlier history.
  - **C** — the answer needed something from outside the case: similar past accidents of the same type in the same conditions, the actual weather report, a rule about fuel reserves.
  - **D** — not obtainable; the NTSB had wreckage or test results you can't see.
- Compute: (share wrong) × (share of wrong that are B or C).
- For each C case, write down which tool would have fixed it. That list, sorted by how often each tool appears, is the order to build the tools in.

Write down: one-shot scores next to the baseline from Session 3; counts of A/B/C/D; the tool priority list.

---

## Session 7 — Surprises and decision (30 min)

- List every oddity found: coding changes over time, duplicate records, mid-air collisions recorded as two cases, reports amended after publication, foreign-registered aircraft, and so on.
- Fill in the assumptions table with pass/fail.
- Apply the decision rule below.
- Write the spike report, two pages at most. Whatever the outcome, this report is something to show in interviews: it demonstrates testing the premise before building on it.

---

## Decision rule (agreed now, before seeing any results)

**Build the agent** if all of these hold: the data is accessible and the factual account is separable (A1–A3); leakage is 20% or less and the give-away phrases can be listed; the single-message model beats the conditional baseline; wrong-rate × (B+C share) is 20% or more; cost is under £0.05 a case.

**Build the classifier version instead** — one model call with a few similar past cases shown as examples, no tool loop — if the single-message model beats the baseline but B+C is thin (under 15%). Still a good project. Just drop the word "agent" and say why.

**Stop** if: the evidence reads like the verdict; or the account can't be separated from the analysis without fragile text-cutting; or the API doesn't work and the only route is the database file with a migration months away.

**Grey zone (B+C between 15% and 20%):** look at *which* cases are in C. If they're the interesting ones — engine failures, flights into bad weather — and the common cases are the trivial majority, build the agent and make accuracy on the uncommon cases the headline number.

---

## Order of execution

Week 1: Sessions 0, 4, then 3 (about 3 hours). These can kill the project. Do nothing else until they're done. Session 4 goes before 3 because it decides which structured fields count as evidence, and the conditional baseline in Session 3 depends on that decision.
Week 2: Sessions 1, 2 (about 2 hours).
Week 3: Sessions 5, 6 (about 2.5 hours).
Week 4: Session 7 and the report (about 30 minutes).

In parallel: the earthquake spike runs on its own seven-step plan. Put the two reports side by side in week 4.
