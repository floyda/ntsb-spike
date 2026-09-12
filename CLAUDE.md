# CLAUDE.md — standing instructions for any agent working in this repo

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
