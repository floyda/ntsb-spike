# NTSB agent — spike report

*Two pages maximum. This is a portfolio artefact whatever the outcome.*

## 1. Question
Can the NTSB aviation investigation data support an agent that determines
probable cause from evidence, evaluated against the NTSB's own published verdicts?

## 2. Decision
One line: build / classifier / stop / grey zone. Then the three numbers that decided it.

## 3. What the data turned out to be
- Access route and its risk (API vs dump; migration date).
- Field completeness (table from `fields.py`).
- Is the factual account separable from the analysis? How?
- Volume per year; time-to-close percentiles; expected live-board resolutions in 6 months.

## 4. Baseline
Table from `baseline.py`: unconditional and conditional modal, top-1/top-3, finding-code P/R.
One sentence on class imbalance.

## 5. Leakage
Rate from the blind-reading sheet. The give-away phrase list. Fields withheld as answer-in-disguise.
What this means for how any accuracy number should be read.

## 6. One-shot ceiling and decidability
One-shot scores next to the baseline.
A/B/C/D counts. Wrong-rate × (B+C).
Tool priority list from the C cases.

## 7. Cost
Per case (typical, long). Full eval with ablations. Weather and docket tool feasibility.

## 8. Surprises
Bullet list. Anything a plan written from outside would have missed.

## 9. What I would build, and what I would not
Concrete. If "build", the first three things. If "classifier", what the agency claim becomes.
If "stop", what the data would have needed to be.
