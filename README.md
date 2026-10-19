# NightAgent

NightAgent is an autonomous research apprentice that learns from experiments and feedback from a supervisor agent.

## What we are building

Two sequential agent roles in one Python harness: a researcher runs bounded experiments, and a supervisor helps articulate the motivation, refine the research question, review measured evidence, and recommend the next step. Humans define the objective, constraints, and budget before execution, then inspect the results. Learning changes stored context, not model weights.

The workshop question is whether an automated supervisor improves research outcomes over a researcher working alone under the same resource limits. We evaluate process reliability and scientific outcomes separately.

## How it works

1. **Supervisor frames the work:** explain why the question matters and turn the initial objective into a testable question and comparison.
2. **Researcher:** choose an approved analysis and parameters that address the question, execute tools, and save results.
3. **Fixed evaluator:** compute metrics and validity checks from the experiment.
4. **Supervisor reviews:** assess what the evidence says about the question, cite run IDs, identify uncertainty, and recommend one next action or stopping. Record any refinement of the question within the original objective.
5. **Harness:** record the framing and experiment/review, enforce limits, and continue or finish with a browser report. Framing calls count toward the shared budget; benchmark criteria remain fixed.

The supervisor's opinion is not ground truth. Agents cannot modify the evaluator or access final test outcomes during search. Suggestions remain hypotheses until supported by evidence; saved lessons include their scope and source runs. Uncertainty can trigger replication within the budget or an inconclusive report.

## Workshop scope and goals

- Start with one project, one model used for both roles, a CLI launcher, and an experiment/review log.
- Present results in a browser through a local web server: plots, metrics, supervisor reviews, findings, limitations, and reproducible artifacts.
- Provide four prewritten tools: `inspect_project`, `run_analysis`, `read_results`, and `save_report`.
- Combine Tutorial 1's tool loop and traces with Tutorial 2's persistent memory and independent evaluation.
- Compare a fixed baseline, researcher alone, and researcher plus supervisor on six predefined cases with two repeats per condition. Match the two agent conditions' model, tools, data, starting history, and resource budgets.
- Score valid actions, evidence use, correction uptake, and stopping separately from independently evaluated scientific outcomes; report cost and runtime.
- Launch once and demonstrate experiments, automated review, revision, and final comparison without human intervention during execution.
- Proposed per-run caps: three research/review rounds, six analyses, 60 seconds per analysis, 15 model calls, and 30,000 total input/output tokens across both roles. Pilot before the proposed $5 evaluation budget.

The scientific task, dataset, analysis script, evaluation metrics, and role owners remain open. Candidate tasks belong in the notes. Generated tools, web/GitHub automation, parallel agents, and browser chat are deferred. The local results viewer is part of the minimum build.

## Project documents and status

- [SPEC.md](SPEC.md): approximately 400-word workshop proposal; a draft, not an implemented system.
- [NOTES.md](NOTES.md): design rationale, evaluation details, candidate tasks, and open decisions.
- [Shared design document](https://docs.google.com/document/d/1tBVSIyVEs3PdngYK7uHr1yEs5l3R0f5kC1OOjMMFqqA/edit?tab=t.tbzfgy1tsr0z): collaborative spec draft.

Status as of 19 October 2026: design documentation only; no agent implementation or evaluation results yet. Next, choose an accessible task and script, assign owners, and build the fixed baseline before adding the adaptive loop.

## Name and guiding ideas

Inspired by [Night Science](https://night-science.org/): explore before judging, improve the question, connect across fields, balance openness with structure, and return to evidence. These are adapted design principles, not claims that the agent already implements them.

## Team 5

Josef Osumeje - josumeje@umich.edu

Ben Moseley

Jake Berv — jacob.berv@gmail.com

Guido Herrera-R - guidohero@hotmail.com

Weiwei Chen - chenww535@gmail.com
