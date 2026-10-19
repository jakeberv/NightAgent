# NightAgent — Team 5

Josef Osumeje, Ben Moseley, Jake Berv, Guido Herrera-R, Weiwei Chen.
Repository: https://github.com/jakeberv/NightAgent

## 1. Task
A supervised research apprentice learns from experiments and feedback across meetings. Input: question, dataset, approved script. Output: reproducible analyses, evidence, next steps. Scientific task remains open.

## 2. Why an agent?
The scientist sets goals; the model chooses bounded analyses and follow-ups. Combine Tutorial 1’s tools/traces with Tutorial 2’s memory. Explore alternatives; test against evidence.

## 3. Tools and data

- inspect_project: project → schema, methods, constraints.
- run_analysis: approved method and validated parameters → run ID, artifacts.
- read_results: run IDs → results and provenance.
- save_report: cited findings and next steps → Markdown report.

Select accessible data/scripts before implementation; save configurations, results, and JSONL traces.
After feedback, extract ≤3 actions/lessons. For each, count unresolved checks for unclear meaning, unclear scope, and conflicting instructions (0–3): ambiguity, not calibrated probability or scientific truth. At zero, seek confirmation; otherwise ask ≤1 consolidated clarification per meeting. Unresolved items stay pending; execute only agreed actions. Confirmed JSON memories retain source/scope; merge duplicates and supersede outdated entries.

## 4. Baseline — Tuesday, 5 PM
CLI: fixed analysis script plus one summarization call.

## 5. Evaluation — Wednesday, 11 AM
Six two-meeting cases (clear/ambiguous/conflicting feedback), two repeats per condition: memory off, unconditional updates, checked updates. Match model, tools, data, prior results, and budgets; script supervisor responses, reset memory between cases, withhold answers, predefine scorecards.
Student (outer loop): trace-backed pass rates for understanding, clarification, correction retention, completion or justified stopping, initiative, honest reporting, escalation. Compare performance before and after feedback; count incorrect memories, missed feedback, repeated errors, supervision burden.
Science (inner loop): verify correctness, provenance, reproducibility. Scientist rates relevance, evidence, added insight versus baseline: 0 absent, 1 partial, 2 strong. Require findings, artifacts, limitations, and a testable next step. Useful negative or inconclusive findings count; unsupported novelty does not.
Report scorecards separately, with cost and runtime. Define scientific checks after task selection.

## 6. Demo — Wednesday, 1 PM
Run analysis; clarify ambiguous feedback; confirm memory; restart. Show whether behavior improves, findings versus baseline, both scorecards, artifacts.

## 7. Risks, limits, roles
Main risk: missing data/script. Tuesday-noon fallback: baseline plus confirmed memory.
One scientist, project, and model; CLI, four prewritten tools. Per cycle: ≤5 model calls including feedback, ≤2 analyses, ≤60 seconds/analysis; return when blocked. Pilot estimates evaluation cost; proposed $5 cap, subject to credits.
Assign owners: harness/memory, tools/data, evaluation/demo. Defer generated tools, web/GitHub automation, multi-agent coordination, GUI.
