# NightAgent

NightAgent is an autonomous research apprentice that learns from experiments and feedback from a supervisor agent.

## What we are building

Two sequential agent roles in one Python harness: a researcher runs bounded experiments, and a supervisor helps articulate the motivation, refine the research question, review measured evidence, and recommend the next step. Humans define the objective, constraints, and budget before execution, then inspect the results. Learning changes stored context, not model weights.

The workshop question is whether an automated supervisor helps a researcher build a better classifier—or achieve comparable performance more reliably—under the same resource limits. The first testbed is building and comparing classification models using a small set of approved approaches. We evaluate research process reliability and held-out classifier performance separately; scientific insights also require evidence explaining when approaches work.

## How it works

1. **Supervisor frames the work:** explain why the question matters and turn the initial objective into a testable question and comparison.
2. **Researcher:** choose an approved classifier approach and parameters that address the question, train it, inspect validation results, and save artifacts.
3. **Fixed evaluator:** compute validation metrics and validity checks during search; independently score the final validation-selected classifier on untouched test data after search ends.
4. **Supervisor reviews:** assess what the evidence says about the question, cite run IDs, identify uncertainty, and recommend one next action or stopping. Record any refinement of the question within the original objective.
5. **Harness:** record the framing and experiment/review, enforce limits, and continue or finish with a browser report. Framing calls count toward the shared budget; benchmark criteria remain fixed.
6. **Post-run evaluator:** read the frozen trace and validation evidence, then score scientific reasoning and interactions with cited events. It cannot influence the agents or see final test scores. Display trace scores separately from classifier performance.

The supervisor's opinion is not ground truth. Agents cannot modify the evaluator or access final test outcomes during search. Suggestions remain hypotheses until supported by evidence; saved lessons include their scope and source runs. Uncertainty can trigger replication within the budget or an inconclusive report.

## Workshop scope and goals

- Start with one researcher and one supervisor, one language model used for both roles, a CLI launcher, and an experiment/review log.
- Use one labeled dataset, two or three approved classifier approaches, bounded parameters, and fixed train/validation/test splits. Fit preprocessing on training data only; choose the primary metric (accuracy or macro-F1) before experiments.
- Present results in a browser through a local web server: plots, metrics, supervisor reviews, findings, limitations, and reproducible artifacts.
- Provide four prewritten tools: `inspect_project`, `run_analysis`, `read_results`, and `save_report`.
- Combine Tutorial 1's tool loop and traces with Tutorial 2's persistent memory and independent evaluation.
- Compare a fixed baseline, researcher alone, and researcher plus supervisor on six predefined cases with two repeats per condition. Match the two agent conditions' model, tools, data, starting history, and resource budgets.
- Score question alignment, experimental design, evidence use, interaction quality, and uncertainty from 0–2 using a fixed post-run rubric. Compare common criteria across conditions; report interaction quality separately and mark it N/A for solo runs. Manually audit sample ratings.
- Use code to check valid actions/references, duplicates, budgets, and stopping. Keep trace overlap/containment optional; differences alone do not imply quality.
- Launch once and demonstrate experiments, automated review, revision, and final comparison without human intervention during execution.
- Proposed search caps: three research/review rounds, six analyses, 60 seconds per analysis, 15 model calls, and 30,000 total input/output tokens across both roles. Meter the bounded post-run evaluator separately, including its cost in the proposed $5 total evaluation budget; pilot before running the suite.

The task family is classification; the dataset, classifier approaches, training script, primary metric, case definitions, and role owners remain open. Dataset candidates belong in the notes. Generated tools, web/GitHub automation, multiple researchers, parallel agents, and browser chat are deferred. The local results viewer is part of the minimum build.

## Project documents and status

- [SPEC.md](SPEC.md): approximately 400-word workshop proposal; a draft, not an implemented system.
- [NOTES.md](NOTES.md): design rationale, evaluation details, candidate tasks, and open decisions.
- [Shared design document](https://docs.google.com/document/d/1tBVSIyVEs3PdngYK7uHr1yEs5l3R0f5kC1OOjMMFqqA/edit?tab=t.tbzfgy1tsr0z): collaborative spec draft.

Status as of 19 October 2026: design documentation only; no agent implementation or evaluation results yet. Next, choose an accessible classification dataset and approved approaches, freeze splits and the primary metric, assign owners, and build the fixed classifier baseline before adding the adaptive loop.

## Name and guiding ideas

Inspired by [Night Science](https://night-science.org/): explore before judging, improve the question, connect across fields, balance openness with structure, and return to evidence. These are adapted design principles, not claims that the agent already implements them.

## Team 5

Josef Osumeje - josumeje@umich.edu

Ben Moseley

Jake Berv — jacob.berv@gmail.com

Guido Herrera-R - guidohero@hotmail.com

Weiwei Chen - chenww535@gmail.com
