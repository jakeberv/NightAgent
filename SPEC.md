# NightAgent — Team 5

Josef Osumeje, Ben Moseley, Jake Berv, Guido Herrera-R, Weiwei Chen.
Repository: https://github.com/jakeberv/NightAgent

## 1. Task
One researcher compares classifiers; one supervisor frames motivation/questions and reviews evidence. Humans set objectives, constraints, and budgets.
Input: labeled dataset, question, approved script. Output: classifier, reproducible history, browser report. Dataset/classifier choices remain open.

## 2. Why agents?
Does supervision improve classifier performance or research reliability? Roles share one language model/harness, combining Tutorial 1’s tools/traces with Tutorial 2’s experience-based adaptation.

## 3. Tools and data

- inspect_project: project → schema, methods, constraints.
- run_analysis: approved classifier/parameters → run ID, validation metrics, artifacts.
- read_results: run IDs → results, history, provenance.
- save_report: evidence-linked findings → Markdown/HTML report.

Choose one dataset, 2–3 approved approaches, bounded parameters, and fixed train/validation/test splits. Fit preprocessing on training only. Fixed code computes metrics; agents cannot alter evaluation or access tests during search.
Loop: supervisor framing → researcher → training/validation → supervisor review. Cite runs, address questions, record uncertainty, recommend one action/stop. Replicate within budget or report inconclusive evidence.
JSONL records questions/revisions, configurations, results, and reviews. Memory retains scoped, evidence-linked lessons; suggestions remain hypotheses until supported.

## 4. Baseline — Tuesday, 5 PM
Fixed classifier plus one model summary; localhost server displays plots/metrics.

## 5. Evaluation — Wednesday, 11 AM
Six cases, two repeats per condition: fixed baseline, researcher alone, researcher plus supervisor. Match briefs, models, tools, splits, history, experiment/model-call/token budgets. Reset memory; freeze evaluation.
Process: post-run LLM evaluator reads frozen traces/results without influencing agents. Score question alignment, experimental design, evidence use, interaction quality, and uncertainty 0–2 with event citations. Mark inapplicable interactions N/A; compare shared criteria separately. Code checks run references, duplicates, budgets/stopping. Manually audit sample ratings; judge scores remain estimates. Trace overlap is optional.
Outcomes: validation selects classifiers; fixed code scores untouched tests using predeclared accuracy/macro-F1. Report reproducibility, uncertainty, cost/runtime, and separate process/outcome scorecards. Scientific insights need supporting evidence. Keep final test scores hidden from the trace-quality evaluator.

## 6. Demo — Wednesday, 1 PM
Launch once; display questions, experiments, reviews, revisions, classifier comparisons, and post-run trace scores without human intervention.

## 7. Risks, limits, roles
Risks: leakage, missing data/scripts, circular criticism, unsupported lessons. Tuesday-noon fallback: fixed baseline/report.
Search caps: ≤3 research/review rounds, ≤6 analyses, ≤60 seconds/analysis, ≤15 model calls including framing, ≤30,000 tokens. Harness enforces limits.
Meter post-run evaluation separately within the proposed $5 total evaluation cap; pilot against available credits.
Assign owners: harness/memory, tools/data, evaluation/report. Defer generated tools, web/GitHub automation, parallel agents, chat UI.
