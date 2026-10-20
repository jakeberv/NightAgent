# NightAgent — Team 5

Josef Osumeje, Ben Moseley, Jake Berv, Guido Herrera-R, Weiwei Chen.
Repository: https://github.com/jakeberv/NightAgent

## 1. Task
For scientists, one researcher explores classification approaches; one supervisor frames/revises questions and reviews evidence. Humans set the broad brief and execution limits; discoveries remain open-ended.
Example: labeled dataset + “Which approaches work well, and why?” → classifier, evidence-linked findings, browser report. Dataset/approaches unchosen; access unchecked.

## 2. Why agents?
Does supervision help? The researcher adaptively chooses configurations, comparisons, replications, or stopping. Roles share one language model/harness: Tutorial 1’s tools/traces plus Tutorial 2’s reflection. Cross-run learning is untested.

## 3. Tools and data

- inspect_project: project → schema, methods, constraints.
- run_analysis: approved classifier/parameters → run ID, validation metrics, artifacts.
- read_results: run IDs → results, history, provenance.
- save_report: evidence-linked findings → Markdown/HTML report.

Fix one dataset, 2–3 approved approaches, parameter bounds, train/validation/test splits, and metric. Fit preprocessing on training only. Agents cannot alter evaluation or access tests during search.
Loop: framing → researcher → training/validation → review. Cite runs, revise hypotheses, record uncertainty, recommend one action/stop. Replicate within budget or report inconclusive evidence; no prescribed winner.
JSONL records questions/revisions, configurations, results, and reviews. Memory retains scoped, evidence-linked lessons; suggestions remain hypotheses until supported.

## 4. Baseline — Tuesday, 5 PM
Fixed classifier plus one model summary; localhost server displays plots/metrics.

## 5. Evaluation — Wednesday, 11 AM
Six cases, two repeats per condition: fixed baseline, researcher alone, researcher plus supervisor. Match briefs, models, tools, splits, history, experiment/model-call/token budgets. Reset memory; freeze evaluation.
Process: read-only post-run LLM scores question alignment, experimental design, evidence use, interaction quality, and uncertainty 0–2 with event citations. Mark inapplicable interactions N/A; compare shared criteria separately. Code checks claims against results, references, budgets/stopping. Audit sample ratings; judge scores are estimates. Trace overlap optional.
Outcomes: validation selects classifiers; fixed code scores untouched tests using predeclared accuracy/macro-F1. Report reproducibility, uncertainty, cost/runtime, and separate process/outcome scorecards. Evaluate supported conclusions, not prescribed discoveries. Hide test scores from the trace judge.

## 6. Demo — Wednesday, 1 PM
Launch once; display questions, experiments, reviews, revisions, classifier comparisons, and trace scores without human intervention.

## 7. Risks, limits, roles
Risks: unavailable data, leakage, unsupported lessons. Tuesday-noon fallback: fixed baseline/report.
Search caps: ≤3 research/review rounds, ≤6 analyses, ≤60 seconds/analysis, ≤15 model calls including framing, ≤30,000 tokens. Harness enforces limits.
Meter post-run evaluation separately within the proposed $5 total evaluation cap; pilot against available credits.
Assign owners: harness/memory, tools/data, evaluation/report. Defer generated tools, web/GitHub automation, parallel agents, chat UI.
