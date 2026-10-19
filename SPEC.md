# NightAgent — Team 5

Josef Osumeje, Ben Moseley, Jake Berv, Guido Herrera-R, Weiwei Chen.
Repository: https://github.com/jakeberv/NightAgent

## 1. Task
An autonomous researcher runs experiments; a supervisor frames the motivation and research question, reviews evidence, and directs follow-ups. Humans set the objective, constraints, and budget.
Input: question, dataset, approved script. Output: reproducible results, experiment history, browser report. Scientific task remains open.

## 2. Why agents?
The supervisor frames a testable question/hypothesis; the researcher chooses experiments. Both share one model/harness. Combine Tutorial 1’s tools/traces with Tutorial 2’s experience-based adaptation.

## 3. Tools and data

- inspect_project: project → schema, methods, constraints.
- run_analysis: approved method/validated parameters → run ID, computed metrics, artifacts.
- read_results: run IDs → results, history, provenance.
- save_report: evidence-linked findings → Markdown/HTML report.

Select data/scripts and verify access before implementation. Fixed code computes metrics; agents cannot change objectives/evaluation or inspect final test outcomes during search.
Loop: supervisor framing → researcher → experiment → computed results → supervisor review. Reviews cite run IDs, address the question, record uncertainty, and recommend one next action or stopping. Uncertainty can trigger replication within budget or an inconclusive report.
Record question revisions, configurations, results, reviews, and JSONL traces. Memory retains scoped, evidence-linked lessons; supervisor suggestions remain hypotheses until supported.

## 4. Baseline — Tuesday, 5 PM
Fixed analysis plus one model summary; localhost server displays saved plots/metrics.

## 5. Evaluation — Wednesday, 11 AM
Six predefined cases, two repeats per condition: fixed baseline, researcher alone, researcher plus supervisor. Match agent briefs, models, tools, data, starting history, experiment and model-call/token budgets. Reset memory between cases; freeze criteria and withhold test answers.
Process: trace-backed pass rates for question–experiment alignment, valid actions, evidence use, correction uptake, and stopping; count repeated errors.
Outcomes: independently compute task metrics on held-out cases; check correctness, reproducibility, and supported findings versus baseline. Report uncertainty, cost, runtime, and both scorecards separately. Supervisor ratings are not ground truth; negative/inconclusive results remain valid. Define scientific metrics after task selection.

## 6. Demo — Wednesday, 1 PM
Launch once; show motivation/question, experiments, supervisor feedback, revisions, and final comparisons in the browser without human intervention.

## 7. Risks, limits, roles
Risks: missing data/script, circular criticism, unsupported lessons. Tuesday-noon fallback: fixed baseline/report.
Per run: ≤3 research/review rounds, ≤6 analyses, ≤60 seconds/analysis, ≤15 model calls including framing, ≤30,000 tokens. Harness enforces limits and stops when blocked.
Pilot evaluation cost; proposed $5 cap, subject to credits.
Assign owners: harness/memory, tools/data, evaluation/report. Defer generated tools, web/GitHub automation, parallel agents, chat UI.
