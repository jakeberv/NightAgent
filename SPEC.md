# NightAgent — Team 5

Josef Osumeje, Ben Moseley, Jake Berv, Guido Herrera-R, Weiwei Chen.
Repository: https://github.com/jakeberv/NightAgent

## 1. Task
One researcher builds and compares classifiers; one supervisor frames motivation/questions, reviews evidence, and directs follow-ups. Humans set objectives, constraints, and budgets.
Input: labeled dataset, question, approved training script. Output: selected classifier, reproducible comparisons, experiment history, browser report. Dataset and classifier choices remain open.

## 2. Why agents?
Does supervision improve classifier performance or research reliability under matched budgets? Roles share one language model/harness, combining Tutorial 1’s tools/traces with Tutorial 2’s experience-based adaptation.

## 3. Tools and data

- inspect_project: project → schema, methods, constraints.
- run_analysis: approved classifier/parameters → run ID, validation metrics, artifacts.
- read_results: run IDs → results, history, provenance.
- save_report: evidence-linked findings → Markdown/HTML report.

Choose one accessible dataset, 2–3 approved approaches, bounded parameters, and fixed train/validation/test splits. Fit preprocessing on training data only. Fixed code computes metrics; agents cannot change evaluation or access tests during search.
Loop: supervisor framing → researcher → training/validation → supervisor review. Reviews cite runs, address the question, record uncertainty, and recommend one action or stopping. Replicate within budget or report inconclusive evidence.
Record question revisions, configurations, results, reviews, and JSONL traces. Memory retains scoped, evidence-linked lessons; supervisor suggestions remain hypotheses until supported.

## 4. Baseline — Tuesday, 5 PM
Fixed classifier plus one model summary; localhost server displays plots/metrics.

## 5. Evaluation — Wednesday, 11 AM
Six predefined cases, two repeats: fixed baseline, researcher alone, researcher plus supervisor. Match agent briefs, language models, tools, splits, history, experiment and model-call/token budgets. Reset memory between cases; freeze evaluation.
Process: trace-backed checks for controlled comparisons, question–experiment alignment, valid actions, evidence use, correction uptake, and stopping; count repeated errors.
Outcomes: select classifiers using validation, then independently score untouched tests with a predeclared metric (accuracy or macro-F1). Report reproducibility, uncertainty, cost, runtime, and separate process/outcome scorecards. Scientific insights require evidence explaining when approaches work; supervisor ratings are not ground truth.

## 6. Demo — Wednesday, 1 PM
Launch once; show motivation/question, experiments, supervisor feedback, revisions, and final comparisons in the browser without human intervention.

## 7. Risks, limits, roles
Risks: leakage, missing data/scripts, circular criticism, unsupported lessons. Tuesday-noon fallback: fixed baseline/report.
Per run: ≤3 research/review rounds, ≤6 analyses, ≤60 seconds/analysis, ≤15 model calls including framing, ≤30,000 tokens. Harness enforces limits and stops when blocked.
Pilot evaluation cost; proposed $5 cap, subject to credits.
Assign owners: harness/memory, tools/data, evaluation/report. Defer generated tools, web/GitHub automation, parallel agents, chat UI.
