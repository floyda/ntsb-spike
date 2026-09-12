# CLAUDE.md — standing instructions for any agent working in this repo

**Status: spike complete, decision: build.** This repo is frozen as the citable record —
see `docs/spike-report.md` (outcome and numbers) and `docs/build-brief.md` (what to
build next). The agent itself is built in `../ntsb-probable-cause/`.

## What this repo is
A pre-build spike. The question is whether NTSB aviation investigation data can support
an agent that determines probable cause from evidence, evaluated against the NTSB's own
verdicts. Nothing here is the agent. Read `docs/spike-plan.md` before doing anything.

## Non-negotiables
1. **Never guess API details.** Base URL, endpoint, parameters, pagination, field names
   come from the NTSB's documentation or from a real response you have saved. If you
   cannot find it, stop and say so. Do not fabricate a plausible endpoint.
2. **The evidence/answer split is sacred.** Analysis text, probable cause, and codes are
   answer fields. They go to a model only via `baseline.py` (which merely counts them) and
   never inside any prompt. `oneshot.build_evidence()` is the only place a model payload is
   assembled. Do not add a second one.
3. **Do not fill in the human labelling sheets.** `labelling/leakage.csv` and
   `labelling/decidability.csv` are for Andy. You may generate them; you may not complete
   the judgement columns. If asked to "help label", produce a separate file with `.model.`
   in the name and say clearly it is a model's opinion, not the ground truth.
4. **Every number reported must come from a script.** If you computed something ad hoc,
   put it in a script first, then quote it. No numbers from memory or estimation.
5. **Record what surprised you** in `docs/session-log.md` after every session. Surprises
   are the point of a spike.
6. **Raw data never goes in git.** `data/raw/` and `data/processed/` are ignored. Keep it that way.
7. **Stop at the stop points** listed in `docs/agent-prompts.md`. Do not run ahead into the
   next session without Andy confirming the previous one.

## API key
The NTSB Enterprise API key is never stored in this repo. Scripts read it from the
`NTSB_API_KEY` environment variable. If it is not set, run the shell function
`load_env_keys` (defined in Andy's ~/.zshrc) to populate it, e.g.:
`zsh -ic 'load_env_keys && python -m ntsb_spike.fetch ...'`

## How to work
- Fill `config.yaml` from real observations, not assumptions. When a field's role is unclear,
  leave it blank and list it under "unmapped" in the session log.
- Prefer small, inspectable steps: fetch one month, look at one record, then widen.
- When a script's TODO can't be resolved from the data you have, say which data would resolve it.
- Time-box: if a session's task is taking more than twice its estimate, stop and report.
- Any document Andy must sign off (reports, briefs, plans) is written in simplified
  technical English: say why each piece of data matters and why each decision is made,
  give examples, and end with a glossary. Andy is learning this domain's jargon; a
  terse expert brief cannot be sized or approved. Numbers stay exact and scripted.

## Commands and data flow

Python ≥3.11. Setup:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e .                    # add the `model` extra (anthropic) to run oneshot.py:
pip install -e ".[model]"
cp config.example.yaml config.yaml  # then fill in after Session 0
```

There are no tests and no linter config. One module per spike task under
`src/ntsb_spike/`, one-off probes under `scripts/`.

The API key is never in the repo; scripts read `NTSB_API_KEY` from the environment. If
it isn't set, load it from Andy's shell function:

```bash
zsh -ic 'load_env_keys && python -m ntsb_spike.fetch 2022-03-01 2022-03-31'
```

Commands, one per module (verified against each module's own usage docstring/argparse):

```bash
python -m ntsb_spike.fetch <start:YYYY-MM-DD> <end:YYYY-MM-DD>  # pull a date range into data/raw/
python -m ntsb_spike.inspect_record [case_id]      # every field of one case, evidence vs answer
python -m ntsb_spike.fields                        # completeness table, narrative-length stats
python -m ntsb_spike.volume                        # cases/year, time-to-close, code distributions, splits
python -m ntsb_spike.baseline                      # unconditional and conditional modal baselines
python -m ntsb_spike.leakage sheet|scan|score       # blind-read sheet, phrase scan, scoring
python -m ntsb_spike.cost                          # token/cost estimate
python -m ntsb_spike.oneshot [--dry] [--ablate ROLE[,ROLE...]] [--out NAME]
                                                    # one-shot model run on 40 stratified held-out cases;
                                                    # --dry builds prompts and asserts no leakage, calls nothing
python -m ntsb_spike.decidability                  # scores labelling/decidability.filled.csv
python scripts/decidability_crosscheck.py          # narrative / no-narrative split, after decidability.py
```

Data flow: `fetch.py` writes `data/raw/fetched=YYYY-MM-DD/cases_*.json` →
`common.load_raw_frame()` flattens with `pd.json_normalize` plus `derived.*` columns
(event codes, finding codes, pilot hours, FAR part, phase of flight) → `apply_filters()`
keeps post-2008, Part 91, Completed → `data/processed/filtered.parquet`, which every
downstream script reads.

Model calls go through the `claude` CLI in headless mode on a subscription (see
`oneshot.call_model`): `claude -p --model … --effort … --tools "" --system-prompt SYSTEM
--output-format json --json-schema <schema>`, with `ANTHROPIC_API_KEY` stripped from the
env so the subscription is used rather than metered API billing. A scheduled build
service needs the real Anthropic API instead, which is why the cost cap matters there.

Key data facts already verified (do not re-probe): base URL `https://api.ntsb.gov/public`,
endpoint `GetCasesByDateRangeV2` with an `Ocp-Apim-Subscription-Key` header and marker-based
pagination (`hasMore` / `nextMarker`) at up to 1000/page; `docketPage` is null on every
record, so the docket URL is built as `https://data.ntsb.gov/Docket?ProjectID={mKey}`;
occurrence code = 3-digit phase prefix + 3-digit event suffix; historical METARs come
byte-identical from the Iowa Mesonet ASOS archive (params in `config.yaml`).
