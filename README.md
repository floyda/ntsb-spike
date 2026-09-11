# ntsb-spike

Pre-build validation for an NTSB probable-cause investigation agent.
Nothing here is the agent. This repo exists to answer one question before
any agent code is written: **do the data and the task support building one?**

Read in this order:

1. `docs/spike-plan.md` — what to check, session by session, and the decision rule.
2. `docs/design-notes.md` — the agent design this spike is validating.
3. `docs/demo-criteria.md` — the evaluation framework (decidability test, demo properties).
4. `docs/assumptions.md` — the live register: fill in pass/fail as sessions complete.
5. `docs/session-log.md` — one entry per session: what was done, what was found.

## Layout

```
docs/               plan, design, criteria, assumptions register, session log, report template
src/ntsb_spike/     small scripts, one per spike task
labelling/          CSV sheets you fill in by hand (leakage, decidability)
data/raw/           raw API responses, date-partitioned (git-ignored)
data/processed/     cleaned tables (git-ignored)
notebooks/          scratch exploration (git-ignored except .gitkeep)
```

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e .
cp config.example.yaml config.yaml   # then fill in after Session 0
```

## Scripts and the sessions they serve

| Script | Session | What it does |
|---|---|---|
| `fetch.py` | 0 | Pull a date range from the API (or load from `avall.zip`) into `data/raw/` |
| `inspect_record.py` | 0 | Print every field of one case, marking structured vs free text |
| `fields.py` | 1 | Completeness table and narrative-length stats |
| `volume.py` | 2 | Cases per year, time-to-close percentiles, code distributions, proposed splits |
| `leakage.py` | 4 | Build the blind-reading sheet and scan for give-away phrases |
| `baseline.py` | 3 | Unconditional and conditional modal baselines |
| `cost.py` | 5 | Token counts and cost estimate for one case and the full eval |
| `oneshot.py` | 6 | Single-message model run on a stratified sample; writes the decidability sheet |
| `decidability.py` | 6 | Reads your filled-in sheet and computes wrong-rate × (B+C share) |

Every script reads `config.yaml` for field names, so the code stays the same
whatever the API actually calls things. **Session 0 is where you fill that in.**

## Rules

- Raw data is never committed. Re-fetch is cheap; a stale copy in git is a liability.
- The answer half (analysis, probable cause, codes) is never passed to any model
  except in `baseline.py`, which only counts it. `oneshot.py` asserts this.
- Every number that ends up in the spike report should be reproducible by one script.
